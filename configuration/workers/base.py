class WorkerBase:
    def __init__(self, name, properties):
        self.name = name
        self.properties = properties

    def __str__(self):
        return self.name
