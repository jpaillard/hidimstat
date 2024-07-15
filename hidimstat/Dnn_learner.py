import numpy as np
from sklearn.base import BaseEstimator
from .Dnn_learner_single import Dnn_learner_single


class Dnn_learner(BaseEstimator):
    """
    This class implements the high-level of the Multi-Layer Perceptron (MLP)
    learner.

    Parameters
    ----------
    encode : bool, default=False
        Whether to encode the categorical outcome.
    do_hypertuning : bool, default=True
        Tuning the hyperparameters of the provided estimator.
    dict_hypertuning : dict, default=None
        The dictionary of hyperparameters to tune.
    n_ensemble : int, default=10
        The number of sub-DNN models to fit to the data.
    min_keep : int, default=10
        The minimal number of sub-DNNs to keep if > 10.
    batch_size : int, default=32
        The number of samples per batch for training.
    batch_size_val : int, default=128
        The number of samples per batch for validation.
    n_epoch : int, default=200
        The number of epochs for the DNN learner(s).
    verbose : int, default=0
        If verbose > 0, the fitted iterations will be printed.
    sampling_with_repitition : bool, default=True
        Application of sampling_with_repitition sampling for the training set.
    split_percentage : float, default=0.8
        The training/validation cut for the provided data.
    problem_type : str, default='regression'
        A classification or a regression problem.
    list_continuous : list, default=None
        The list of continuous variables.
    list_grps : list of lists, default=None
        A list collecting the indices of the groups' variables
        while applying the stacking method.
    beta1 : float, default=0.9
        The exponential decay rate for the first moment estimates.
    beta2 : float, default=0.999
        The exponential decay rate for the second moment estimates.
    lr : float, default=1e-3
        The learning rate.
    epsilon : float, default=1e-8
        A small constant added to the denominator to prevent division by zero.
    l1_weight : float, default=1e-2
        The L1-regularization paramter for weight decay.
    l2_weight : float, default=0
        The L2-regularization paramter for weight decay.
    n_jobs : int, default=1
        The number of workers for parallel processing.
    group_stacking : bool, default=False
        Apply the stacking-based method for the provided groups.
    input_dimensions : list, default=None
        The cumsum of inputs after the linear sub-layers.
    random_state : int, default=2023
        Fixing the seeds of the random generator.
    """

    def __init__(
        self,
        encode=False,
        do_hypertuning=False,
        dict_hypertuning=None,
        n_ensemble=10,
        min_keep=10,
        batch_size=32,
        batch_size_val=128,
        n_epoch=200,
        verbose=0,
        sampling_with_repitition=True,
        split_percentage=0.8,
        problem_type="regression",
        list_continuous=None,
        list_grps=None,
        beta1=0.9,
        beta2=0.999,
        lr=1e-2,
        epsilon=1e-8,
        l1_weight=1e-2,
        l2_weight=1e-2,
        n_jobs=1,
        group_stacking=False,
        input_dimensions=None,
        random_state=2023,
    ):
        self.list_estimators = []
        self.encode = encode
        self.do_hypertuning = do_hypertuning
        self.dict_hypertuning = dict_hypertuning
        self.n_ensemble = n_ensemble
        self.min_keep = min_keep
        self.batch_size = batch_size
        self.batch_size_val = batch_size_val
        self.n_epoch = n_epoch
        self.verbose = verbose
        self.sampling_with_repitition = sampling_with_repitition
        self.split_percentage = split_percentage
        self.problem_type = problem_type
        self.list_grps = list_grps
        self.beta1 = beta1
        self.beta2 = beta2
        self.lr = lr
        self.epsilon = epsilon
        self.l1_weight = l1_weight
        self.l2_weight = l2_weight
        self.list_continuous = list_continuous
        self.n_jobs = n_jobs
        self.group_stacking = group_stacking
        self.input_dimensions = input_dimensions
        self.random_state = random_state
        self.pred = [None] * n_ensemble
        self.enc_y = []
        self.is_encoded = False
        self.dim_repeat = 1

    def fit(self, X, y=None):
        """
        Build the DNN learner with the training set (X, y)

        Parameters
        ----------
        X : {pandas dataframe, array-like, sparse matrix} of shape (n_samples,
        n_features)
            The training input samples.
        y : array-like of shape (n_samples,) or (n_samples, n_outputs),
        default=None
            The target values (class labels in classification, real numbers in
            regression).

        Returns
        -------
        self : object
            Returns self.
        """
        if (len(X.shape) != 3) or (X.shape[0] != y.shape[-1]):
            X = np.squeeze(X)
            X = np.array([X for i in range(y.shape[-1])])
            self.dim_repeat = y.shape[-1]

        self.list_estimators = [None] * y.shape[-1]
        self.X_test = [None] * y.shape[-1]

        for y_col in range(y.shape[-1]):
            self.list_estimators[y_col] = Dnn_learner_single(
                encode=self.encode,
                do_hypertuning=self.do_hypertuning,
                dict_hypertuning=self.dict_hypertuning,
                n_ensemble=self.n_ensemble,
                min_keep=self.min_keep,
                batch_size=self.batch_size,
                batch_size_val=self.batch_size_val,
                n_epoch=self.n_epoch,
                verbose=self.verbose,
                sampling_with_repitition=self.sampling_with_repitition,
                split_percentage=self.split_percentage,
                problem_type=self.problem_type,
                list_continuous=self.list_continuous,
                list_grps=self.list_grps,
                beta1=self.beta1,
                beta2=self.beta2,
                lr=self.lr,
                epsilon=self.epsilon,
                l1_weight=self.l1_weight,
                l2_weight=self.l2_weight,
                n_jobs=self.n_jobs,
                group_stacking=self.group_stacking,
                input_dimensions=self.input_dimensions,
                random_state=self.random_state,
            )

            self.list_estimators[y_col].fit(X[y_col, ...], y[:, [y_col]])

        return self

    def hyper_tuning(
        self,
        X_train,
        y_train,
        X_valid,
        y_valid,
        list_hyper=None,
        random_state=None,
    ):
        """
        This function tunes the provided hyperparameters of the DNN learner.

        Parameters
        ----------
        X_train : {array-like, sparse matrix} of shape (n_train_samples, n_features)
            The training input samples.
        y_train : array-like of shape (n_train_samples,) or (n_train_samples, n_outputs)
            The target values (class labels in classification, real numbers in
            regression) for the training samples.
        X_train : {array-like, sparse matrix} of shape (n_valid_samples, n_features)
            The validation input samples.
        y_train : array-like of shape (n_valid_samples,) or (n_valid_samples, n_outputs)
            The target values (class labels in classification, real numbers in
            regression) for the validation samples.
        list_hyper : list of tuples, default=None
            The list of tuples for the hyperparameters values.
        random_state : int, default=None
            Fixing the seeds of the random generator.
        """
        estimator = Dnn_learner_single(
            encode=self.encode,
            do_hypertuning=self.do_hypertuning,
            dict_hypertuning=self.dict_hypertuning,
            n_ensemble=self.n_ensemble,
            min_keep=self.min_keep,
            batch_size=self.batch_size,
            batch_size_val=self.batch_size_val,
            n_epoch=self.n_epoch,
            verbose=self.verbose,
            sampling_with_repitition=self.sampling_with_repitition,
            split_percentage=self.split_percentage,
            problem_type=self.problem_type,
            list_continuous=self.list_continuous,
            list_grps=self.list_grps,
            beta1=self.beta1,
            beta2=self.beta2,
            lr=self.lr,
            epsilon=self.epsilon,
            l1_weight=self.l1_weight,
            l2_weight=self.l2_weight,
            n_jobs=self.n_jobs,
            group_stacking=self.group_stacking,
            input_dimensions=self.input_dimensions,
            random_state=self.random_state,
        )
        return estimator.hyper_tuning(
            X_train, y_train, X_valid, y_valid, list_hyper, random_state
        )

    def predict(self, X, scale=True):
        """
        This function predicts the regression target for the input samples X.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_test_samples, n_features),
            default=None
            The input samples.
        scale : bool, default=True
            Whether to scale the continuous input variables.

        Returns
        -------
        predictions : {array-like, sparse matrix)
            The average predictions across the sub-DNN models.
        """
        if isinstance(X, list):
            X = [self.check_X_dim(el) for el in X]
        else:
            X = self.check_X_dim(X)
        list_res = []
        for estimator_ind, estimator in enumerate(self.list_estimators):
            if isinstance(X, list):
                curr_X = [el[estimator_ind, ...] for el in X]
                list_res.append(estimator.predict(curr_X, scale))
            else:
                list_res.append(estimator.predict(X[estimator_ind, ...], scale))
                self.X_test[estimator_ind] = estimator.X_test.copy()
        return np.array(list_res)

    def predict_proba(self, X, scale=True):
        """
        This function predicts the class probabilities for the input samples X.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_test_samples, n_features),
            default=None
            The input samples.
        scale : bool, default=True
            Whether to scale the continuous input variables.

        Returns
        -------
        predictions : {array-like, sparse matrix)
            The average predictions across the sub-DNN models.
        """
        if isinstance(X, list):
            X = [self.check_X_dim(el) for el in X]
        else:
            X = self.check_X_dim(X)

        list_res = []
        for estimator_ind, estimator in enumerate(self.list_estimators):
            if isinstance(X, list):
                curr_X = [el[estimator_ind, ...] for el in X]
                list_res.append(estimator.predict_proba(curr_X, scale))
            else:
                list_res.append(estimator.predict_proba(X[estimator_ind, ...], scale))
                self.X_test[estimator_ind] = estimator.X_test.copy()
        return np.squeeze(np.array(list_res))

    def set_params(self, **kwargs):
        """
        This function sets the parameters for the DNN estimator
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
            for estimator in self.list_estimators:
                setattr(estimator, key, value)

    def check_X_dim(self, X):
        """
        This function checks for the compatibility of the dimensions of X
        """
        if (len(X.shape) != 3) or (X.shape[0] != self.dim_repeat):
            X = np.squeeze(X)
            X = np.array([X for i in range(self.dim_repeat)])

        return X

    def encode_outcome(self, y, train=True):
        """
        This function encodes the categorical outcome

        Parameters
        ----------
        y : ndarray
            The categorical outcome.
        train : bool, default=True
            Whether to fit or not the encoder.
        """
        for y_col in range(y.shape[-1]):
            y_enc = self.list_estimators[y_col].encode_outcome(y, train=train)
        return y_enc
