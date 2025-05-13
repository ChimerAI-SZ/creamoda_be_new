from src.alg.replicate import Replicate
class ReplicateAdapter:
    _adapter = None

    def __init__(self):
        self.replicate = Replicate()

    @classmethod
    def get_adapter(cls):
        if cls._adapter is None:
            cls._adapter = ReplicateAdapter()
        return cls._adapter

    def remove_background(self, image_url: str) -> bytes:   
        return self.replicate.remove_background(image_url)
