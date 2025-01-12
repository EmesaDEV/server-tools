==============
JSONify Stored
==============

.. !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fserver--tools-lightgray.png?logo=github
    :target: https://github.com/OCA/server-tools/tree/14.0/jsonifier_stored
    :alt: OCA/server-tools
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/server-tools-14-0/server-tools-14-0-jsonifier_stored
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runbot-Try%20me-875A7B.png
    :target: https://runbot.odoo-community.org/runbot/149/14.0
    :alt: Try me on Runbot

|badge1| |badge2| |badge3| |badge4| |badge5| 

This module provides a mixin to help storing JSON data.

The idea is that you can pre-compute some data
so that the system does not have to compute it
every time it is asked, for instance, by an external service.

Inspired by the machinery in `connector_search_engine`
(which ideally should be refactored on `jsonifier_stored`)
and by a first experiment for v12 done here
https://github.com/OCA/server-tools/pull/1926.

**Table of contents**

.. contents::
   :local:

Usage
=====

This is a technical module,
hence you should take care of extending your models w/ `jsonifier.stored.mixin`.

Your module should also provide a `base_jsonify` compatible exporter
by overriding `_jsonify_get_exporter`.

The cron "JSONify stored - Recompute data for all models"
will recompute data for all inheriting models.

Computations is delegated to queue jobs and by default each job will compute 5 records.
You can tweak this by passing `chunk_size` to `cron_update_json_data_for`.

If your model has a lang field, before jobs are created,
records will be grouped by language.

NOTE: if the model is already existing in your DB is recommended to use
`jsonifier_stored.hooks.add_jsonifier_column` function
to prevent Odoo to compute all data when you update your module.

Known issues / Roadmap
======================

- Make the jsonified_data field recomputed when:
  - any of the exported field is modified
  - the related export is changed (exported fields definition)
- This module is inspired by `connector_search_engine`
  which should be refactored on top of this.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/server-tools/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and welcomed
`feedback <https://github.com/OCA/server-tools/issues/new?body=module:%20jsonifier_stored%0Aversion:%2014.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* Camptocamp

Contributors
~~~~~~~~~~~~

* Simone Orsi <simone.orsi@camptocamp.com>
* Matthieu Méquignon <matthieu.mequignon@camptocamp.com>

Maintainers
~~~~~~~~~~~

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

.. |maintainer-simahawk| image:: https://github.com/simahawk.png?size=40px
    :target: https://github.com/simahawk
    :alt: simahawk
.. |maintainer-mmequignon| image:: https://github.com/mmequignon.png?size=40px
    :target: https://github.com/mmequignon
    :alt: mmequignon

Current `maintainers <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-simahawk| |maintainer-mmequignon| 

This module is part of the `OCA/server-tools <https://github.com/OCA/server-tools/tree/14.0/jsonifier_stored>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
