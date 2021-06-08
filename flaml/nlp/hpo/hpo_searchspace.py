from collections import OrderedDict

from ..huggingface.trainer import TrainerForAutoTransformers
from ray import tune
from transformers import TrainingArguments

from .grid_searchspace_auto import AutoGridSearchSpace


def hpo_space_custom(**custom_hpo_args):
    assert "hpo_space" in custom_hpo_args
    custom_search_space = custom_hpo_args["hpo_space"]
    return custom_search_space


def bounded_gridunion(logger=None,
                      model_type=None,
                      model_size_type=None,
                      dataset_name=None,
                      subdataset_name=None,
                      **custom_hpo_args):
    assert "bound" in custom_hpo_args
    gridunion_space = HPO_SEARCH_SPACE_MAPPING["uni"](logger,
                                                      model_type,
                                                      model_size_type,
                                                      dataset_name,
                                                      subdataset_name,
                                                      **custom_hpo_args)
    for each_key in custom_hpo_args["bound"].keys():
        if "u" in custom_hpo_args["bound"][each_key]:
            upper = custom_hpo_args["bound"][each_key]["u"]
        else:
            upper = 100000
        if "l" in custom_hpo_args["bound"][each_key]:
            lower = custom_hpo_args["bound"][each_key]["l"]
        else:
            lower = -100000
        original_space = sorted(gridunion_space[each_key])
        upper_id = len(original_space)
        for x in range(len(original_space)):
            if original_space[x] > upper:
                upper_id = x
                break
        lower_id = 0
        for x in range(len(original_space) - 1, -1, -1):
            if original_space[x] < lower:
                lower_id = x
                break
        gridunion_space[each_key] = original_space[lower_id:upper_id]
    return gridunion_space


def hpo_space_gridunion(logger=None,
                        model_type=None,
                        model_size_type=None,
                        dataset_name=None,
                        subdataset_name=None,
                        **custom_hpo_args):
    output_config = {}
    for each_model_type in {"electra", "roberta", "bert"}:
        # if each_model_type == model_type: continue
        this_config = AutoGridSearchSpace.from_model_and_dataset_name(
            each_model_type, model_size_type, dataset_name, subdataset_name, "hpo")
        from ..utils import merge_dicts
        output_config = merge_dicts(output_config, this_config)
        default_values = {}
        """
            adding the default configuration from transformers/training_args.py into hpo space 
        """
        training_args = TrainingArguments(output_dir=".")
        for each_hp in output_config.keys():
            try:
                default_values[each_hp] = [getattr(training_args, each_hp)]
            except AttributeError:
                pass

        output_config = merge_dicts(output_config, default_values)

    return output_config


def hpo_space_gridunion_smoke_test(
        logger=None,
        model_type=None,
        model_size_type=None,
        dataset_name=None,
        subdataset_name=None,
        **custom_hpo_args):
    return {'learning_rate':
                [1e-5],
            'weight_decay': [0.0],
            'adam_epsilon': [1e-08],
            'warmup_ratio': [0.1],
            'per_device_train_batch_size': [2],
            'hidden_dropout_prob': [0.1],
            'attention_probs_dropout_prob': [0.1],
            'num_train_epochs': [0.1]}


def hpo_space_generic(logger=None,
                      model_type=None,
                      model_size_type=None,
                      dataset_name=None,
                      subdataset_name=None,
                      **custom_hpo_args):
    output_config = {
        "learning_rate": {"l": 1e-6, "u": 1e-3, "space": "log"},
        "num_train_epochs": {"l": 1.0, "u": 10.0, "space": "log"},
        "per_device_train_batch_size": [4, 8, 16, 32, 48],
        "warmup_ratio": {"l": 0.0, "u": 0.3, "space": "linear"},
        "weight_decay": {"l": 0.0, "u": 0.3, "space": "linear"}
    }
    return output_config


def hpo_space_generic_grid(logger=None,
                           model_type=None,
                           model_size_type=None,
                           dataset_name=None,
                           subdataset_name=None,
                           **custom_hpo_args):
    output_config = {
        "learning_rate": [1e-5, 2e-5, 3e-5, 4e-5, 5e-5, 1e-4, 1.5e-4],
        "num_train_epochs": [3, 10],
        "per_device_train_batch_size": [16, 32],
        "warmup_ratio": [0, 0.06, 0.1],
        "weight_decay": [0, 0.1]
    }
    return output_config


def hpo_space_small(logger=None,
                    model_type=None,
                    model_size_type=None,
                    dataset_name=None,
                    subdataset_name=None,
                    **custom_hpo_args):
    config_json = AutoGridSearchSpace.from_model_and_dataset_name(
        model_type, model_size_type, dataset_name, subdataset_name, "hpo")
    output_config = {}

    for each_hp in config_json.keys():
        if each_hp == "learning_rate":
            if len(config_json[each_hp]) > 1:
                output_config[each_hp] = {"l": 3e-5, "u": 1.5e-4, "space": "log"}
            else:
                output_config[each_hp] = config_json[each_hp]
        elif each_hp == "num_train_epochs":
            output_config[each_hp] = {"l": 2.0, "u": 4.0, "space": "linear"}
        elif each_hp == "per_device_train_batch_size":
            output_config[each_hp] = [16, 32, 64]
        elif each_hp == "warmup_ratio":
            output_config[each_hp] = {"l": 0.0, "u": 0.2, "space": "linear"}
        elif each_hp == "weight_decay":
            output_config[each_hp] = {"l": 0.0, "u": 0.3, "space": "linear"}
        else:
            output_config[each_hp] = config_json[each_hp]

    return output_config


HPO_SEARCH_SPACE_MAPPING = OrderedDict(
    [
        ("uni", hpo_space_gridunion),
        ("gnr", hpo_space_generic),
        ("uni_test", hpo_space_gridunion_smoke_test),
        ("cus", hpo_space_custom),
        ("buni", bounded_gridunion)
    ]
)


class AutoHPOSearchSpace:
    """
    This is a class for getting the hpo search space based on the search space mode
    (a string variable) instantiated as one of the HPO search spaces of the library when
    created with the `~flaml.nlp.hpo.AutoHPOSearchSpace.from_model_and_dataset_name` method.

    This class cannot be instantiated directly using ``__init__()`` (throws an error).
    """

    def __init__(self):
        raise EnvironmentError(
            "AutoHPOSearchSpace is designed to be instantiated "
            "using the `AutoHPOSearchSpace.from_config_and_method_name(cls, logger,hpo_searchspace_name,"
            "model_type,model_size_type,dataset_name,subdataset_name = None,**custom_hpo_args)` methods."
        )

    @classmethod
    def from_model_and_dataset_name(cls,
                                    logger,
                                    hpo_searchspace_mode,
                                    model_type,
                                    model_size_type,
                                    dataset_name,
                                    subdataset_name=None,
                                    **custom_hpo_args):
        """
        Instantiate one of the classes for getting the hpo search space from the search space name, model type,
        model size type, dataset name and sub dataset name

        Args:
            logger:
                Reference to the logger

            hpo_searchspace_mode:
                A string variable which is name of the hpo search space, e.g., "uni"

            model_type:
                A string variable which is the type of the model, e.g., "electra"

            model_size_type:
                A string variable which is the type of the model size, e.g., "small"

            dataset_name:
                A string variable which is the dataset name, e.g., "glue"

            subdataset_name:
                A string variable which is the sub dataset name,e.g., "rte"

            custom_hpo_args:
                Any additional keyword argument to be used for the function for the HPO search space

        Example:
            >>> AutoHPOSearchSpace.from_model_and_dataset_name(logger, "uni", "electra", "small", "glue", "rte")
        """

        if hpo_searchspace_mode in HPO_SEARCH_SPACE_MAPPING.keys():
            try:
                hpo_space = HPO_SEARCH_SPACE_MAPPING[hpo_searchspace_mode](
                    logger,
                    model_type,
                    model_size_type,
                    dataset_name,
                    subdataset_name,
                    **custom_hpo_args)
                return hpo_space
            except KeyError:
                return None
        raise ValueError(
            "Unrecognized method {},{} for this kind of AutoHPOSearchSpace: {}.\n"
            "Method name should be one of {}.".format(
                hpo_searchspace_name, dataset_name, cls.__name__,
                ", ".join(c.__name__ for c in HPO_SEARCH_SPACE_MAPPING.keys())
            )
        )
