from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
    Slot,
)


class WorkerSignals(QObject):

    finished = Signal(object)

    error = Signal(str)


class Worker(QRunnable):

    def __init__(
        self,
        function,
    ):

        super().__init__()

        self.function = function

        self.signals = WorkerSignals()


    @Slot()
    def run(self):

        try:

            result = self.function()

            self.signals.finished.emit(
                result
            )

        except Exception as error:

            self.signals.error.emit(
                str(error)
            )