import os
import shutil

import pytest

from seldonian.models.models import LinearRegressionModel
from seldonian.RL.RL_model import RL_model
from seldonian.RL.Agents.Policies.Softmax import DiscreteSoftmax
from seldonian.RL.Env_Description.Env_Description import Env_Description
from seldonian.RL.Env_Description.Spaces import Discrete_Space
from seldonian.models import objectives
from seldonian.utils.io_utils import *
from seldonian.dataset import *
from seldonian.parse_tree.parse_tree import *
from seldonian.spec import *

from experiments.experiment_utils import supervised_initial_solution_fn

@pytest.fixture
def gpa_regression_spec():
    print("Setup gpa_regression_spec")
    
    def spec_maker(constraint_strs,deltas):

        data_pth = 'static/datasets/supervised/GPA/gpa_regression_dataset_1000points.csv'
        metadata_pth = 'static/datasets/supervised/GPA/metadata_regression.json'

        meta = load_supervised_metadata(metadata_pth)           

        # Load dataset from file
        loader = DataSetLoader(
            regime=meta.regime)

        dataset = loader.load_supervised_dataset(
            filename=data_pth,
            metadata_filename=metadata_pth,
            file_type='csv')

        spec = createSupervisedSpec(
            dataset=dataset,
            metadata_pth=metadata_pth,
            constraint_strs=constraint_strs,
            deltas=deltas,
            save=False,
            verbose=False)

        spec.optimization_hyperparams = {
                'lambda_init'   : 0.5,
                'alpha_theta'   : 0.005,
                'alpha_lamb'    : 0.005,
                'beta_velocity' : 0.9,
                'beta_rmsprop'  : 0.95,
                'num_iters'     : 50,
                'use_batches'   : False,
                'gradient_library': "autograd",
                'hyper_search'  : None,
                'verbose'       : True,
            }
        return spec
    
    yield spec_maker
    print("Teardown gpa_regression_spec")
    
@pytest.fixture
def gpa_regression_addl_datasets_spec():
    print("Setup gpa_regression_addl_datasets_spec")

    def spec_maker(constraint_strs,deltas):

        # data_pth = 'static/datasets/supervised/GPA/gpa_regression_dataset_1000points.csv'
        # metadata_pth = 'static/datasets/supervised/GPA/metadata_regression.json'
        data_pth = "static/datasets/supervised/GPA/gpa_regression_dataset.csv"
        metadata_pth = "static/datasets/supervised/GPA/metadata_regression.json"

        metadata_dict = load_json(metadata_pth)
        regime = metadata_dict["regime"]
        sub_regime = metadata_dict["sub_regime"]
        all_col_names = metadata_dict["all_col_names"]
        sensitive_col_names = metadata_dict["sensitive_col_names"]

        regime = "supervised_learning"

        model = LinearRegressionModel()

        # Mean squared error
        primary_objective = objectives.Mean_Squared_Error

        # Load dataset from file
        loader = DataSetLoader(regime=regime)

        orig_dataset = loader.load_supervised_dataset(
            filename=data_pth, metadata_filename=metadata_pth, file_type="csv"
        )

        # The new primary dataset has no sensitive attributes
        primary_meta = orig_dataset.meta
        primary_meta.all_col_names = [x for x in primary_meta.all_col_names if x not in primary_meta.sensitive_col_names]
        primary_meta.sensitive_col_names = []
        primary_dataset = SupervisedDataSet(
            features=orig_dataset.features,
            labels=orig_dataset.labels,
            sensitive_attrs=[],
            num_datapoints=orig_dataset.num_datapoints,
            meta=primary_meta
        )

        # Now make a dataset to use for bounding the base nodes
        # Take 80% of the original data
        orig_features = orig_dataset.features
        orig_labels = orig_dataset.labels
        orig_sensitive_attrs = orig_dataset.sensitive_attrs
        num_datapoints_new = int(round(len(orig_features)*0.8))
        rand_indices = np.random.choice(
            a=range(len(orig_features)),
            size=num_datapoints_new,
            replace=False
        )
        new_features = orig_features[rand_indices]
        new_labels = orig_labels[rand_indices]
        new_sensitive_attrs = orig_sensitive_attrs[rand_indices]
        new_meta = SupervisedMetaData(
            sub_regime=sub_regime,
            all_col_names=all_col_names,
            feature_col_names=primary_meta.feature_col_names,
            label_col_names=primary_meta.label_col_names,
            sensitive_col_names=sensitive_col_names,
        )
        new_dataset = SupervisedDataSet(
            features=new_features,
            labels=new_labels,
            sensitive_attrs=new_sensitive_attrs,
            num_datapoints=num_datapoints_new,
            meta=new_meta

        )

        # For each constraint, make a parse tree 
        parse_trees = []
        for ii in range(len(constraint_strs)):
            constraint_str = constraint_strs[ii]
            delta = deltas[ii]
            # Create parse tree object
            parse_tree = ParseTree(
                delta=delta,
                regime="supervised_learning",
                sub_regime="regression",
                columns=sensitive_col_names,
            )

            parse_tree.build_tree(constraint_str=constraint_str)
            parse_trees.append(parse_tree)

        # For each base node in each parse_tree, 
        # add this new dataset to additional_datasets dictionary
        # It is possible that when a parse tree is built, 
        # the constraint string it stores is different than the one that 
        # was used as input. This is because the parser may simplify the expression
        # Therefore, we want to use the constraint string attribute of the built parse 
        # tree as the key to the additional_datasets dict.

        additional_datasets = {}
        for pt in parse_trees:
            additional_datasets[pt.constraint_str] = {}
            base_nodes_this_tree = list(pt.base_node_dict.keys())
            for bn in base_nodes_this_tree:
                additional_datasets[pt.constraint_str][bn] = {
                    "dataset": new_dataset
                }
        frac_data_in_safety = 0.6

        # Create spec object
        spec = SupervisedSpec(
            dataset=primary_dataset,
            additional_datasets=additional_datasets,
            model=model,
            parse_trees=parse_trees,
            sub_regime="regression",
            frac_data_in_safety=frac_data_in_safety,
            primary_objective=primary_objective,
            use_builtin_primary_gradient_fn=True,
            initial_solution_fn=supervised_initial_solution_fn,
            optimization_technique="gradient_descent",
            optimizer="adam",
            optimization_hyperparams={
                "lambda_init": np.array([0.5 for _ in range(len(constraint_strs))]),
                "alpha_theta": 0.005,
                "alpha_lamb": 0.005,
                "beta_velocity": 0.9,
                "beta_rmsprop": 0.95,
                "num_iters": 200,
                "use_batches": False,
                "gradient_library": "autograd",
                "hyper_search": None,
                "verbose": True,
            },
        )
        
        return spec
    
    yield spec_maker
    print("Teardown gpa_regression_addl_datasets_spec")
    

@pytest.fixture
def gpa_classification_spec():
    print("Setup gpa_classification_spec")
    
    def spec_maker(constraint_strs,deltas):

        data_pth = 'static/datasets/supervised/GPA/gpa_classification_dataset_1000points.csv'
        metadata_pth = 'static/datasets/supervised/GPA/metadata_classification.json'

        (regime, sub_regime, all_col_names, feature_col_names,
            label_col_names, sensitive_col_names) = load_supervised_metadata(
                metadata_pth)

        # Load dataset from file
        loader = DataSetLoader(
            regime=regime)

        dataset = loader.load_supervised_dataset(
            filename=data_pth,
            metadata_filename=metadata_pth,
            file_type='csv')

        spec = createSupervisedSpec(
            dataset=dataset,
            metadata_pth=metadata_pth,
            constraint_strs=constraint_strs,
            deltas=deltas,
            save=False,
            verbose=False)

        spec.optimization_hyperparams = {
                'lambda_init'   : 0.5,
                'alpha_theta'   : 0.005,
                'alpha_lamb'    : 0.005,
                'beta_velocity' : 0.9,
                'beta_rmsprop'  : 0.95,
                'num_iters'     : 50,
                'use_batches'   : False,
                'gradient_library': "autograd",
                'hyper_search'  : None,
                'verbose'       : True,
            }
        return spec
    
    yield spec_maker
    print("Teardown gpa_classification_spec")
    

@pytest.fixture
def gridworld_spec():
    print("Setup gridworld_spec")
    
    def spec_maker(constraint_strs,deltas):

        episodes_file = 'static/datasets/RL/gridworld/gridworld_100episodes.pkl'
        episodes = load_pickle(episodes_file)
        meta = RLMetaData(
            all_col_names=["episode_index", "O", "A", "R", "pi_b"]
        )
        dataset = RLDataSet(episodes=episodes,meta=meta)
        # Initialize policy
        num_states = 9
        observation_space = Discrete_Space(0, num_states-1)
        action_space = Discrete_Space(0, 3)
        env_description =  Env_Description(observation_space, action_space)
        policy = DiscreteSoftmax(hyperparam_and_setting_dict={},
            env_description=env_description)
        env_kwargs={'gamma':0.9}
        save_dir = '.'

        spec = createRLSpec(
            dataset=dataset,
            policy=policy,
            constraint_strs=constraint_strs,
            deltas=deltas,
            env_kwargs=env_kwargs,
            save=False,
            verbose=True)

        return spec
    
    yield spec_maker
    print("Teardown gridworld_spec")
    

@pytest.fixture
def experiment(request):
    results_dir = request.param
    """ Fixture to create and then remove results_dir and any files it may contain"""
    print("Setup experiment fixture")
    os.makedirs(results_dir,exist_ok=True)
    yield
    print("Teardown experiment fixture")
    shutil.rmtree(results_dir)


