from .models import TestRun, TestFailure, Builder

class MariaDBRouter:
    """
    Database router directing TestRun and TestFailure models to MariaDB.
    """

    def db_for_read(self, model, **hints):
        if model in [TestRun, TestFailure, Builder]:
            return 'mariadb'
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations between TestRun and TestFailure, but not with other models
        if obj1._meta.model in [TestRun, TestFailure] and obj2._meta.model in [TestRun, TestFailure]:
            return True
        elif obj1._meta.model not in [TestRun, TestFailure] and obj2._meta.model not in [TestRun, TestFailure]:
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Do not allow migrations as they are managed=False
        return False
