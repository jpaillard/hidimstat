import numpy as np
from joblib import Parallel, delayed
from sklearn.base import (
    BaseEstimator,
    TransformerMixin,
    check_is_fitted,
    clone,
)
from sklearn.metrics import mean_squared_error


class CPI(BaseEstimator, TransformerMixin):
    """
    Conditional Permutation Importance (CPI) algorithm.
    :footcite:t:`Chamma_NeurIPS2023` and for group-level see
    :footcite:t:`Chamma_AAAI2024`.


    Parameters
    ----------
    estimator: scikit-learn compatible estimator
        The predictive model.
    imputation_model: scikit-learn compatible estimator or list of
    estimators
        The model(s) used to estimate the covariates. If a single estimator is
        provided, it will be cloned for each covariate. Otherwise, a list of
        potentially different estimators can be provided, the length of the
        list must match the number of covariates.
    n_perm: int, default=50
        Number of permutations to perform.
    groups: dict, default=None
        Dictionary of groups for the covariates. The keys are the group names
        and the values are lists of covariate indices.
    loss: callable, default=mean_squared_error
        Loss function to evaluate the model performance.
    score_proba: bool, default=False
        Whether to use the predict_proba method of the estimator.
    random_state: int, default=None
        Random seed for the permutation.
    n_jobs: int, default=1
        Number of jobs to run in parallel.

    References
    ----------
    .. footbibliography::
    """

    def __init__(
        self,
        estimator,
        imputation_model,
        n_perm: int = 50,
        groups: dict = None,
        loss: callable = mean_squared_error,
        score_proba: bool = False,
        random_state: int = None,
        n_jobs: int = 1,
    ):

        check_is_fitted(estimator)
        self.estimator = estimator
        self.imputation_model = imputation_model
        if isinstance(self.imputation_model, list):
            self.list_imputation_mod = self.imputation_model
        else:
            self.list_imputation_mod = []
        self.n_perm = n_perm
        self.groups = groups
        self.random_state = random_state
        self.loss = loss
        self.score_proba = score_proba
        self.n_jobs = n_jobs

        self.rng = np.random.RandomState(random_state)

    def fit(self, X, y):
        """
        Fit the covariate estimators to predict each group of covariates from
        the others.
        """
        if self.groups is None:
            self.nb_groups = X.shape[1]
            self.groups = {j: [j] for j in range(self.nb_groups)}
        else:
            self.nb_groups = len(self.groups)
        # create a list of covariate estimators for each group if not provided
        if len(self.list_imputation_mod) == 0:
            self.list_imputation_mod = [
                clone(self.imputation_model) for _ in range(self.nb_groups)
            ]

        def joblib_fit_one_gp(estimator, X, y, j):
            """
            Fit a single covariate estimator to predict a single group of
            covariates.
            """
            X_j = X[:, self.groups[j]].copy()
            X_minus_j = np.delete(X, self.groups[j], axis=1)
            estimator.fit(X_minus_j, X_j)
            return estimator

        # Parallelize the fitting of the covariate estimators
        self.list_imputation_mod = Parallel(n_jobs=self.n_jobs)(
            delayed(joblib_fit_one_gp)(estimator, X, y, j)
            for j, estimator in enumerate(self.list_imputation_mod)
        )

        return self

    def predict(self, X, y=None):
        """
        Compute the CPI importance scores. For each group of covariates, the
        residuals are computed using the covariate estimators. The residuals
        are then permuted and the model is re-evaluated. The importance score
        is the difference between the loss of the model with the original data
        and the loss of the model with the permuted data.

        Parameters
        ----------
        X: array-like of shape (n_samples, n_features)
            The input samples.
        y: array-like of shape (n_samples,)
            The target values.

        Returns
        -------
        output_dict: dict
            A dictionary containing the following keys:
            - 'loss_reference': the loss of the model with the original data.
            - 'loss_perm': a dictionary containing the loss of the model with
            the permuted data for each group.
            - 'importance': the importance scores for each group.
        """
        if len(self.list_imputation_mod) == 0:
            raise ValueError("fit must be called before predict")
        for m in self.list_imputation_mod:
            check_is_fitted(m)

        def joblib_predict_one_gp(imputation_model, X, j):
            """
            Compute the prediction of the model with the permuted data for a
            single group of covariates.
            """
            list_y_pred_perm = []
            X_j = X[:, self.groups[j]].copy()
            X_minus_j = np.delete(X, self.groups[j], axis=1)
            X_j_hat = imputation_model.predict(X_minus_j).reshape(X_j.shape)
            residual_j = X_j - X_j_hat

            group_ids = self.groups[j]
            non_group_ids = np.delete(np.arange(X.shape[1]), group_ids)

            for _ in range(self.n_perm):
                X_j_perm = X_j_hat + self.rng.permutation(residual_j)
                X_perm = np.empty_like(X)
                X_perm[:, non_group_ids] = X_minus_j
                X_perm[:, group_ids] = X_j_perm

                if self.score_proba:
                    y_pred_perm = self.estimator.predict_proba(X_perm)
                else:
                    y_pred_perm = self.estimator.predict(X_perm)
                list_y_pred_perm.append(y_pred_perm)

            return np.array(list_y_pred_perm)

        # Parallelize the computation of the importance scores for each group
        out_list = Parallel(n_jobs=self.n_jobs)(
            delayed(joblib_predict_one_gp)(imputation_model, X, j)
            for j, imputation_model in enumerate(self.list_imputation_mod)
        )

        return np.stack(out_list, axis=0)

    def score(self, X, y):
        """
        Compute the importance scores for each group of covariates.

        Parameters
        ----------
        X: array-like of shape (n_samples, n_features)
            The input samples.
        y: array-like of shape (n_samples,)
            The target values.

        Returns
        -------
        out_dict: dict
            A dictionary containing the following keys:
            - 'loss_reference': the loss of the model with the original data.
            - 'loss_perm': a dictionary containing the loss of the model with
            the permuted data for each group.
            - 'importance': the importance scores for each group.
        """
        check_is_fitted(self.estimator)
        if len(self.list_imputation_mod) == 0:
            raise ValueError("fit must be called before score")
        for m in self.list_imputation_mod:
            check_is_fitted(m)

        out_dict = dict()

        if self.score_proba:
            y_pred = self.estimator.predict_proba(X)
        else:
            y_pred = self.estimator.predict(X)

        loss_reference = self.loss(y_true=y, y_pred=y_pred)
        out_dict["loss_reference"] = loss_reference

        y_pred_perm = self.predict(X, y)

        out_dict["loss_perm"] = dict()
        for j, y_pred_j in enumerate(y_pred_perm):
            list_loss_perm = []
            for y_pred_perm in y_pred_j:
                list_loss_perm.append(self.loss(y_true=y, y_pred=y_pred_perm))
            out_dict["loss_perm"][j] = np.array(list_loss_perm)

        out_dict["importance"] = np.array(
            [
                np.mean(out_dict["loss_perm"][j]) - loss_reference
                for j in range(self.nb_groups)
            ]
        )

        return out_dict
