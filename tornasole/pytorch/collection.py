from tornasole.core.collection import Collection as BaseCollection
from tornasole.core.collection import CollectionKeys
from tornasole.core.collection_manager import CollectionManager as BaseCollectionManager


class Collection(BaseCollection):
    def add_module_tensors(self, module, inputs=False, outputs=False):
        if inputs:
            input_tensor_regex = module._get_name() + "_input_*"
            self.include(input_tensor_regex)
        if outputs:
            output_tensor_regex = module._get_name() + "_output"
            self.include(output_tensor_regex)


class CollectionManager(BaseCollectionManager):
    def __init__(self, create_default=True):
        super().__init__(create_default=create_default)
        # self.export_only_once = True
        if create_default:
            self._register_default_collections()

    def _register_default_collections(self):
        self.get(CollectionKeys.WEIGHTS).include("^(?!gradient).*weight")
        self.get(CollectionKeys.BIASES).include("^(?!gradient).*bias")
        self.get(CollectionKeys.GRADIENTS).include("^gradient")
        self.get(CollectionKeys.LOSSES).include("[Ll]oss")

    def create_collection(self, name):
        super().create_collection(name, cls=Collection)

    @classmethod
    def load(cls, filename):
        return super().load(cls, filename, Collection)

    @classmethod
    def load_from_string(cls, s):
        return super().load(cls, s, Collection)


_collection_manager = CollectionManager()


def load_collections(path):
    global _collection_manager
    _collection_manager = CollectionManager.load(path)


def reset_collections():
    global _collection_manager
    del _collection_manager
    _collection_manager = CollectionManager()


def add_to_collection(collection_name, args):
    get_collection(collection_name).add(args)


def get_collection_manager():
    return _collection_manager


def add_to_default_collection(args):
    add_to_collection(CollectionKeys.DEFAULT, args)


def get_collection(collection_name):
    return _collection_manager.get(collection_name, create=True)


def get_collections():
    return _collection_manager.collections
