# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import UserError

FIELDS_BLACKLIST = [
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "display_name",
    "__last_update",
]
# Used for performance, to avoid a dictionary instanciation when we need an
# empty dict to simplify algorithms
EMPTY_DICT = {}


class DictDiffer(object):
    """Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current = set(current_dict)
        self.set_past = set(past_dict)
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return {o for o in self.intersect if self.past_dict[o] != self.current_dict[o]}

    def unchanged(self):
        return {o for o in self.intersect if self.past_dict[o] == self.current_dict[o]}


class AuditlogRule(models.Model):
    _name = "auditlog.rule"
    _description = "Auditlog - Rule"

    name = fields.Char(required=True, states={"subscribed": [("readonly", True)]})
    model_id = fields.Many2one(
        "ir.model",
        "Model",
        help="Select model for which you want to generate log.",
        states={"subscribed": [("readonly", True)]},
        ondelete="set null",
        index=True,
    )
    model_name = fields.Char(readonly=True)
    model_model = fields.Char(string="Technical Model Name", readonly=True)
    user_ids = fields.Many2many(
        "res.users",
        "audittail_rules_users",
        "user_id",
        "rule_id",
        string="Users",
        help="if  User is not added then it will applicable for all users",
        states={"subscribed": [("readonly", True)]},
    )
    log_read = fields.Boolean(
        "Log Reads",
        help=(
            "Select this if you want to keep track of read/open on any "
            "record of the model of this rule"
        ),
        states={"subscribed": [("readonly", True)]},
    )
    log_write = fields.Boolean(
        "Log Writes",
        default=True,
        help=(
            "Select this if you want to keep track of modification on any "
            "record of the model of this rule"
        ),
        states={"subscribed": [("readonly", True)]},
    )
    log_unlink = fields.Boolean(
        "Log Deletes",
        default=True,
        help=(
            "Select this if you want to keep track of deletion on any "
            "record of the model of this rule"
        ),
        states={"subscribed": [("readonly", True)]},
    )
    log_create = fields.Boolean(
        "Log Creates",
        default=True,
        help=(
            "Select this if you want to keep track of creation on any "
            "record of the model of this rule"
        ),
        states={"subscribed": [("readonly", True)]},
    )
    log_type = fields.Selection(
        [("full", "Full log"), ("fast", "Fast log")],
        string="Type",
        required=True,
        default="full",
        help=(
            "Full log: make a diff between the data before and after "
            "the operation (log more info like computed fields which were "
            "updated, but it is slower)\n"
            "Fast log: only log the changes made through the create and "
            "write operations (less information, but it is faster)"
        ),
        states={"subscribed": [("readonly", True)]},
    )

    state = fields.Selection(
        [("draft", "Draft"), ("subscribed", "Subscribed")],
        required=True,
        default="draft",
    )
    action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Action",
        states={"subscribed": [("readonly", True)]},
    )
    capture_record = fields.Boolean(
        help="Select this if you want to keep track of Unlink Record",
    )
    users_to_exclude_ids = fields.Many2many(
        "res.users",
        string="Users to Exclude",
        context={"active_test": False},
        states={"subscribed": [("readonly", True)]},
    )

    fields_to_exclude_ids = fields.Many2many(
        "ir.model.fields",
        domain="[('model_id', '=', model_id)]",
        string="Fields to Exclude",
        states={"subscribed": [("readonly", True)]},
    )

    _sql_constraints = [
        (
            "model_uniq",
            "unique(model_id)",
            (
                "There is already a rule defined on this model\n"
                "You cannot define another: please edit the existing one."
            ),
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Update the registry when a new rule is created.  Where relevant the
        subscribe() method is called as this also creates a shortcut to the view
        of the results of the rule.
        """
        for vals in vals_list:
            if "model_id" not in vals or not vals["model_id"]:
                raise UserError(_("No model defined to create line."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        new_records = super().create(vals_list)
        for new_record in new_records.filtered(lambda rec: rec.state == "subscribed"):
            new_record.subscribe()
        self.env.registry.clear_caches()
        return new_records

    def write(self, vals):
        """Update the registry when existing rules are updated."""
        if "model_id" in vals:
            if not vals["model_id"]:
                raise UserError(_("Field 'model_id' cannot be empty."))
            model = self.env["ir.model"].sudo().browse(vals["model_id"])
            vals.update({"model_name": model.name, "model_model": model.model})
        res = super().write(vals)
        self.env.registry.clear_caches()
        return res

    def unlink(self):
        """Unsubscribe rules before removing them."""
        self.unsubscribe()
        self.env.registry.clear_caches()
        return super(AuditlogRule, self).unlink()

    @api.model
    def get_auditlog_fields(self, model):
        """
        Get the list of auditlog fields for a model
        By default it is all stored fields only, but you can
        override this.
        """
        return list(
            n
            for n, f in model._fields.items()
            if (not f.compute and not f.related) or f.store
        )

    def create_logs(
        self,
        uid,
        res_model,
        res_ids,
        method,
        old_values=None,
        new_values=None,
        additional_log_values=None,
    ):
        """Create logs. `old_values` and `new_values` are dictionaries, e.g:
        {RES_ID: {'FIELD': VALUE, ...}}
        """
        if old_values is None:
            old_values = EMPTY_DICT
        if new_values is None:
            new_values = EMPTY_DICT
        log_model = self.env["auditlog.log"]
        http_request_model = self.env["auditlog.http.request"]
        http_session_model = self.env["auditlog.http.session"]
        model_model = self.env[res_model]
        model_id = self.pool._auditlog_model_cache[res_model]
        auditlog_rule = self.env["auditlog.rule"].search([("model_id", "=", model_id)])
        fields_to_exclude = auditlog_rule.fields_to_exclude_ids.mapped("name")
        for res_id in res_ids:
            name = model_model.browse(res_id).name_get()
            res_name = name and name[0] and name[0][1]
            vals = {
                "name": res_name,
                "model_id": model_id,
                "res_id": res_id,
                "method": method,
                "user_id": uid,
                "http_request_id": http_request_model.current_http_request(),
                "http_session_id": http_session_model.current_http_session(),
            }
            vals.update(additional_log_values or {})
            log = log_model.create(vals)
            diff = DictDiffer(
                new_values.get(res_id, EMPTY_DICT), old_values.get(res_id, EMPTY_DICT)
            )
            if method == "create":
                self._create_log_line_on_create(
                    log, diff.added(), new_values, fields_to_exclude
                )
            elif method == "read":
                self._create_log_line_on_read(
                    log,
                    list(old_values.get(res_id, EMPTY_DICT).keys()),
                    old_values,
                    fields_to_exclude,
                )
            elif method == "write":
                self._create_log_line_on_write(
                    log, diff.changed(), old_values, new_values, fields_to_exclude
                )
            elif method == "unlink" and auditlog_rule.capture_record:
                self._create_log_line_on_read(
                    log,
                    list(old_values.get(res_id, EMPTY_DICT).keys()),
                    old_values,
                    fields_to_exclude,
                )

    def _get_field(self, model, field_name):
        if not hasattr(self.pool, "_auditlog_field_cache"):
            self.pool._auditlog_field_cache = {}
        cache = self.pool._auditlog_field_cache
        if field_name not in cache.get(model.model, {}):
            cache.setdefault(model.model, {})
            # - we use 'search()' then 'read()' instead of the 'search_read()'
            #   to take advantage of the 'classic_write' loading
            # - search the field in the current model and those it inherits
            field_model = self.env["ir.model.fields"].sudo()
            all_model_ids = [model.id]
            all_model_ids.extend(model.inherited_model_ids.ids)
            field = field_model.search(
                [("model_id", "in", all_model_ids), ("name", "=", field_name)]
            )
            # The field can be a dummy one, like 'in_group_X' on 'res.users'
            # As such we can't log it (field_id is required to create a log)
            if not field:
                cache[model.model][field_name] = False
            else:
                field_data = field.read(load="_classic_write")[0]
                cache[model.model][field_name] = field_data
        return cache[model.model][field_name]

    def _create_log_line_on_read(
        self, log, fields_list, read_values, fields_to_exclude
    ):
        """Log field filled on a 'read' operation."""
        log_line_model = self.env["auditlog.log.line"]
        fields_to_exclude = fields_to_exclude + FIELDS_BLACKLIST
        for field_name in fields_list:
            if field_name in fields_to_exclude:
                continue
            field = self._get_field(log.model_id, field_name)
            # not all fields have an ir.models.field entry (ie. related fields)
            if field:
                log_vals = self._prepare_log_line_vals_on_read(log, field, read_values)
                log_line_model.create(log_vals)

    def _prepare_log_line_vals_on_read(self, log, field, read_values):
        """Prepare the dictionary of values used to create a log line on a
        'read' operation.
        """
        vals = {
            "field_id": field["id"],
            "log_id": log.id,
            "old_value": read_values[log.res_id][field["name"]],
            "old_value_text": read_values[log.res_id][field["name"]],
            "new_value": False,
            "new_value_text": False,
        }
        if field["relation"] and "2many" in field["ttype"]:
            old_value_text = (
                self.env[field["relation"]].browse(vals["old_value"]).name_get()
            )
            vals["old_value_text"] = old_value_text
        return vals

    def _create_log_line_on_write(
        self, log, fields_list, old_values, new_values, fields_to_exclude
    ):
        """Log field updated on a 'write' operation."""
        log_line_model = self.env["auditlog.log.line"]
        fields_to_exclude = fields_to_exclude + FIELDS_BLACKLIST
        for field_name in fields_list:
            if field_name in fields_to_exclude:
                continue
            field = self._get_field(log.model_id, field_name)
            # not all fields have an ir.models.field entry (ie. related fields)
            if field:
                log_vals = self._prepare_log_line_vals_on_write(
                    log, field, old_values, new_values
                )
                log_line_model.create(log_vals)

    def _prepare_log_line_vals_on_write(self, log, field, old_values, new_values):
        """Prepare the dictionary of values used to create a log line on a
        'write' operation.
        """
        vals = {
            "field_id": field["id"],
            "log_id": log.id,
            "old_value": old_values[log.res_id][field["name"]],
            "old_value_text": old_values[log.res_id][field["name"]],
            "new_value": new_values[log.res_id][field["name"]],
            "new_value_text": new_values[log.res_id][field["name"]],
        }
        # for *2many fields, log the name_get
        if log.log_type == "full" and field["relation"] and "2many" in field["ttype"]:
            # Filter IDs to prevent a 'name_get()' call on deleted resources
            existing_ids = self.env[field["relation"]]._search(
                [("id", "in", vals["old_value"])]
            )
            old_value_text = []
            if existing_ids:
                existing_values = (
                    self.env[field["relation"]].browse(existing_ids).name_get()
                )
                old_value_text.extend(existing_values)
            # Deleted resources will have a 'DELETED' text representation
            deleted_ids = set(vals["old_value"]) - set(existing_ids)
            for deleted_id in deleted_ids:
                old_value_text.append((deleted_id, "DELETED"))
            vals["old_value_text"] = old_value_text
            new_value_text = (
                self.env[field["relation"]].browse(vals["new_value"]).name_get()
            )
            vals["new_value_text"] = new_value_text
        return vals

    def _create_log_line_on_create(
        self, log, fields_list, new_values, fields_to_exclude
    ):
        """Log field filled on a 'create' operation."""
        log_line_model = self.env["auditlog.log.line"]
        fields_to_exclude = fields_to_exclude + FIELDS_BLACKLIST
        for field_name in fields_list:
            if field_name in fields_to_exclude:
                continue
            field = self._get_field(log.model_id, field_name)
            # not all fields have an ir.models.field entry (ie. related fields)
            if field:
                log_vals = self._prepare_log_line_vals_on_create(log, field, new_values)
                log_line_model.create(log_vals)

    def _prepare_log_line_vals_on_create(self, log, field, new_values):
        """Prepare the dictionary of values used to create a log line on a
        'create' operation.
        """
        vals = {
            "field_id": field["id"],
            "log_id": log.id,
            "old_value": False,
            "old_value_text": False,
            "new_value": new_values[log.res_id][field["name"]],
            "new_value_text": new_values[log.res_id][field["name"]],
        }
        if log.log_type == "full" and field["relation"] and "2many" in field["ttype"]:
            new_value_text = (
                self.env[field["relation"]].browse(vals["new_value"]).name_get()
            )
            vals["new_value_text"] = new_value_text
        return vals

    def subscribe(self):
        """Subscribe Rule for auditing changes on model and apply shortcut
        to view logs on that model.
        """
        act_window_model = self.env["ir.actions.act_window"]
        for rule in self:
            if rule.state == "subscribed" and rule.action_id:
                continue
            # Create a shortcut to view logs
            domain = "[('model_id', '=', %s), ('res_id', '=', active_id)]" % (
                rule.model_id.id
            )
            vals = {
                "name": _("View logs"),
                "res_model": "auditlog.log",
                "binding_model_id": rule.model_id.id,
                "domain": domain,
            }
            act_window = act_window_model.sudo().create(vals)
            rule.write({"state": "subscribed", "action_id": act_window.id})
        return True

    def unsubscribe(self):
        """Unsubscribe Auditing Rule on model."""
        for rule in self:
            # Remove the shortcut to view logs
            act_window = rule.action_id
            if act_window:
                act_window.unlink()
        return self.write({"state": "draft"})

    @api.model
    def _update_vals_list(self, vals_list):
        # Odoo supports empty recordset assignment (while it doesn't handle
        # non-empty recordset ¯\_(ツ)_/¯ ), it could be an Odoo issue, but in
        # the meanwhile we have to handle this case to avoid errors when using
        # ``deepcopy`` to log data.
        for vals in vals_list:
            for fieldname, fieldvalue in vals.items():
                if isinstance(fieldvalue, models.BaseModel) and not fieldvalue:
                    vals[fieldname] = False
        return vals_list
