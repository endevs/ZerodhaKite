class Strategy:
    def __init__(self, parameters):
        self.parameters = parameters

    def execute(self):
        raise NotImplementedError("Each strategy must implement the execute method.")
