"""
Clustering Algorithms Module

This module provides production-ready implementation of various clustering algorithms:
https://scikit-learn.org/stable/api/sklearn.cluster.html#module-sklearn.cluster

Available clustering algorithms at the moment:

1. KMeans
2. SpectralClustering
3. DBSCAN 

Author: Dr. Philip Naderev P. Lagniton
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans as SKKMeans, DBSCAN as SKDBSCAN, SpectralClustering as SKSpecClust
from sklearn.exceptions import NotFittedError
from sklearn.metrics import silhouette_score, davies_bouldin_score
from typing import Optional, Tuple, Dict, Any, List, Union
import warnings
from sklearn.preprocessing import StandardScaler

class KMeansClusterer:

    """Production-ready implementation of K-Means clustering algorithm.
    
    This class provides a robust implementation of K-Means clustering with:
    - Comprehensive parameter validation
    - Detailed documentation
    - Configurable parameters
    - Support for various initialization methods
    - Evaluation metrics
    - Visualization capabilities
    
    Example:
        clusterer = KMeansClusterer(n_clusters=3)
        clusterer.fit(data)
        labels = clusterer.predict(data)
        fig = clusterer.plot_clusters()
    """
    
    def __init__(self,
                 n_clusters: int = 8,
                 init: str = 'k-means++',
                 n_init: int = 10,
                 max_iter: int = 300,
                 tol: float = 1e-4,
                 random_state: Optional[int] = None,
                 store_training_data: bool = False):
        """
        Initialize the K-Means clusterer with specified parameters.
        
        Args:
            n_clusters: Number of clusters to form
            init: Method for initialization ('k-means++', 'random', or ndarray)
            n_init: Number of time the k-means algorithm will be run
            max_iter: Maximum number of iterations
            tol: Relative tolerance for convergence
            random_state: Random seed for reproducibility
            store_training_data: Whether to store training data for visualization
        """
        # Validate parameters
        if n_clusters <= 0:
            raise ValueError("n_clusters must be positive")
        if n_init <= 0:
            raise ValueError("n_init must be positive")
        if max_iter <= 0:
            raise ValueError("max_iter must be positive")
        if tol <= 0:
            raise ValueError("tol must be positive")
            
        self.n_clusters = n_clusters
        self.init = init
        self.n_init = n_init
        self.max_iter = max_iter
        self.tol = tol
        self.random_state = random_state
        self.store_training_data = store_training_data
        self.model = None
        self.is_fitted = False
        self.X_train = None
        self.cluster_centers_ = None
        self.labels_ = None
        self.inertia_ = None
        self.n_features_in_ = None
    
    def fit(self, X: np.ndarray) -> 'KMeansClusterer':
        """
        Compute k-means clustering.
        
        Args:
            X: Training instances to cluster, shape (n_samples, n_features)
            
        Returns:
            self: The fitted clusterer
            
        Raises:
            ValueError: If input data is invalid
        """
        # Input validation
        self._validate_data(X)
        
        # Store training data if requested
        if self.store_training_data:
            self.X_train = X.copy()
        
        # Create and fit the model
        self.model = SKKMeans(
            n_clusters=self.n_clusters,
            init=self.init,
            n_init=self.n_init,
            max_iter=self.max_iter,
            tol=self.tol,
            random_state=self.random_state
        )
        
        self.model.fit(X)
        
        # Store relevant attributes
        self.cluster_centers_ = self.model.cluster_centers_
        self.labels_ = self.model.labels_
        self.inertia_ = self.model.inertia_
        self.n_features_in_ = self.model.n_features_in_
        
        self.is_fitted = True
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict the closest cluster each sample in X belongs to.
        
        Args:
            X: New data to predict, shape (n_samples, n_features)
            
        Returns:
            Index of the cluster each sample belongs to
            
        Raises:
            NotFittedError: If the model isn't fitted
            ValueError: If input is invalid
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before predict()")
        
        self._validate_data(X)
        
        return self.model.predict(X)
    
    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """
        Compute cluster centers and predict cluster index for each sample.
        
        Args:
            X: Training instances to cluster, shape (n_samples, n_features)
            
        Returns:
            Index of the cluster each sample belongs to
        """
        self.fit(X)
        return self.labels_
    
    def get_params(self) -> Dict[str, Any]:
        """Get parameters for this estimator."""
        return {
            'n_clusters': self.n_clusters,
            'init': self.init,
            'n_init': self.n_init,
            'max_iter': self.max_iter,
            'tol': self.tol,
            'random_state': self.random_state,
            'store_training_data': self.store_training_data
        }
    
    def set_params(self, **params) -> 'KMeansClusterer':
        """Set the parameters of this estimator."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
    
    def plot_clusters(self, 
                     X: Optional[np.ndarray] = None,
                     title: str = "K-Means Clustering",
                     figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Create a visualization of the clustered data.
        
        Args:
            X: Data to plot. If None, uses stored training data.
            title: Title for the plot
            figsize: Size of the figure (width, height) in inches
            
        Returns:
            matplotlib Figure object
            
        Raises:
            ValueError: If no data is available to plot
            NotFittedError: If the model isn't fitted
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before plot_clusters()")
        
        # Determine which data to plot
        if X is None:
            if self.X_train is None:
                raise ValueError("No data available to plot. Either provide X or initialize with store_training_data=True")
            X = self.X_train
        
        self._validate_data(X)
        
        # Get labels for the data we're plotting
        labels = self.predict(X) if X is not self.X_train else self.labels_
        
        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot all points colored by cluster
        scatter = ax.scatter(
            X[:, 0], 
            X[:, 1], 
            c=labels,
            cmap='viridis',
            s=30,
            alpha=0.8
        )
        
        # Plot cluster centers if available
        if hasattr(self, 'cluster_centers_') and self.cluster_centers_ is not None:
            ax.scatter(
                self.cluster_centers_[:, 0],
                self.cluster_centers_[:, 1],
                s=200,
                c='red',
                marker='X',
                edgecolor='k',
                label='Cluster Centers'
            )
        
        ax.set_xlabel("Feature 1")
        ax.set_ylabel("Feature 2")
        ax.set_title(f"{title} (k={self.n_clusters})")
        
        # Add legend for cluster centers
        if hasattr(self, 'cluster_centers_') and self.cluster_centers_ is not None:
            ax.legend(loc="best")
        
        plt.tight_layout()
        return fig
    
    def evaluate(self, X: np.ndarray) -> Dict[str, float]:
        """
        Evaluate clustering performance using standard metrics.
        
        Args:
            X: Data to evaluate, shape (n_samples, n_features)
            
        Returns:
            Dictionary of evaluation metrics
            
        Raises:
            NotFittedError: If the model isn't fitted
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before evaluate()")
        
        self._validate_data(X)
        
        labels = self.predict(X)
        
        # Skip metrics that require multiple clusters
        metrics = {}
        if len(np.unique(labels)) > 1:
            metrics['silhouette_score'] = silhouette_score(X, labels)
            metrics['davies_bouldin_score'] = davies_bouldin_score(X, labels)
        
        metrics['inertia'] = self.model.inertia_
        
        return metrics
    
    def _validate_data(self, X: np.ndarray) -> None:
        """Validate input data format and content."""
        if not isinstance(X, np.ndarray):
            raise ValueError(f"Expected numpy array, got {type(X)}")
        
        if X.ndim != 2:
            raise ValueError(f"Expected 2D array, got {X.ndim}D array")
        
        if np.isnan(X).any() or np.isinf(X).any():
            raise ValueError("Input contains NaN or infinity values")
        
        # For visualization, we need at least 2 features
        if X.shape[1] < 2 and self.store_training_data:
            raise ValueError("At least 2 features required for visualization")
    
    def tune_parameters(self, 
                       X: np.ndarray,
                       n_clusters_range: range = range(2, 11),
                       metric: str = 'silhouette',
                       cv_folds: int = 3) -> Dict[str, Any]:
        """
        Perform hyperparameter tuning for K-Means clustering.
        
        Args:
            X: Data to tune on, shape (n_samples, n_features)
            n_clusters_range: Range of n_clusters values to try
            metric: Evaluation metric to optimize ('silhouette', 'davies_bouldin', 'inertia')
            cv_folds: Number of cross-validation folds
            
        Returns:
            Dictionary containing best parameters and evaluation results
        """
        self._validate_data(X)
        
        if X.shape[0] < 10:
            raise ValueError("Not enough samples for meaningful hyperparameter tuning")
        
        results = []
        best_score = -float('inf') if metric in ['silhouette'] else float('inf')
        best_params = None
        
        # Standardize data for consistent clustering
        X_scaled = StandardScaler().fit_transform(X)
        
        for n_clusters in n_clusters_range:
            if n_clusters >= X.shape[0]:
                continue
                
            try:
                model = SKKMeans(
                    n_clusters=n_clusters,
                    init=self.init,
                    n_init=self.n_init,
                    max_iter=self.max_iter,
                    random_state=self.random_state
                )
                labels = model.fit_predict(X_scaled)
                
                # Skip if all points are in one cluster
                if len(np.unique(labels)) < 2:
                    continue
                    
                # Calculate the requested metric
                if metric == 'silhouette':
                    score = silhouette_score(X_scaled, labels)
                    is_better = (score > best_score)
                elif metric == 'davies_bouldin':
                    score = davies_bouldin_score(X_scaled, labels)
                    is_better = (score < best_score)
                elif metric == 'inertia':
                    score = model.inertia_
                    is_better = (score < best_score)
                else:
                    raise ValueError(f"Unknown metric: {metric}")
                
                results.append({
                    'n_clusters': n_clusters,
                    'score': score
                })
                
                if is_better:
                    best_score = score
                    best_params = {'n_clusters': n_clusters}
                    
            except Exception as e:
                warnings.warn(f"Failed to evaluate n_clusters={n_clusters}: {str(e)}")
                continue
        
        # Update model with best parameters if found
        if best_params:
            self.n_clusters = best_params['n_clusters']
            self.fit(X_scaled)
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'metric_used': metric,
            'all_results': results
        }
    
    def plot_tuning_results(self, 
                           tuning_results: Dict[str, Any],
                           figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Visualize hyperparameter tuning results for K-Means.
        
        Args:
            tuning_results: Results from tune_parameters()
            figsize: Size of the figure
            
        Returns:
            matplotlib Figure object
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Extract data for plotting
        n_clusters_vals = [r['n_clusters'] for r in tuning_results['all_results']]
        scores = [r['score'] for r in tuning_results['all_results']]
        
        # Plot the scores
        ax.plot(n_clusters_vals, scores, 'o-', color='blue', linewidth=2)
        
        # Highlight best parameters
        if tuning_results['best_params']:
            ax.plot(
                tuning_results['best_params']['n_clusters'],
                tuning_results['best_score'],
                'o', 
                markersize=12, 
                markerfacecolor='red',
                markeredgecolor='k',
                label='Best Parameters'
            )
        
        ax.set_xlabel('Number of Clusters (k)')
        ax.set_ylabel(tuning_results['metric_used'].replace('_', ' ').title())
        ax.set_title(f'K-Means Parameter Tuning ({tuning_results["metric_used"]} score)')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()
        
        plt.tight_layout()
        return fig


class DBSCANClusterer:
    """Production-ready implementation of DBSCAN clustering algorithm.
    
    This class provides a robust implementation of DBSCAN with:
    - Comprehensive parameter validation
    - Detailed documentation
    - Configurable parameters
    - Support for different distance metrics
    - Evaluation metrics
    - Visualization capabilities
    
    Example:
        clusterer = DBSCANClusterer(eps=0.5, min_samples=5)
        clusterer.fit(data)
        labels = clusterer.labels_
        fig = clusterer.plot_clusters()
    """
    
    def __init__(self,
                 eps: float = 0.5,
                 min_samples: int = 5,
                 metric: str = 'euclidean',
                 metric_params: Optional[Dict] = None,
                 algorithm: str = 'auto',
                 leaf_size: int = 30,
                 p: Optional[float] = None,
                 n_jobs: Optional[int] = None,
                 store_training_data: bool = False):
        """
        Initialize the DBSCAN clusterer with specified parameters.
        
        Args:
            eps: The maximum distance between two samples for them to be 
                considered as in the same neighborhood
            min_samples: The number of samples in a neighborhood for a point 
                to be considered as a core point
            metric: The metric to use for distance computation
            metric_params: Additional keyword arguments for the metric function
            algorithm: The algorithm to be used for nearest neighbor search
            leaf_size: Leaf size passed to BallTree or cKDTree
            p: Power parameter for Minkowski metric
            n_jobs: The number of parallel jobs to run
            store_training_data: Whether to store training data for visualization
        """
        # Validate parameters
        if eps <= 0:
            raise ValueError("eps must be positive")
        if min_samples <= 0:
            raise ValueError("min_samples must be positive")
        if leaf_size <= 0:
            raise ValueError("leaf_size must be positive")
            
        self.eps = eps
        self.min_samples = min_samples
        self.metric = metric
        self.metric_params = metric_params
        self.algorithm = algorithm
        self.leaf_size = leaf_size
        self.p = p
        self.n_jobs = n_jobs
        self.store_training_data = store_training_data
        self.model = None
        self.is_fitted = False
        self.X_train = None
        self.labels_ = None
        self.core_sample_indices_ = None
        self.components_ = None
        self.n_features_in_ = None
    
    def fit(self, X: np.ndarray) -> 'DBSCANClusterer':
        """
        Perform DBSCAN clustering.
        
        Args:
            X: Training instances to cluster, shape (n_samples, n_features)
            
        Returns:
            self: The fitted clusterer
            
        Raises:
            ValueError: If input data is invalid
        """
        # Input validation
        self._validate_data(X)
        
        # Store training data if requested
        if self.store_training_data:
            self.X_train = X.copy()
        
        # Create and fit the model
        self.model = SKDBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric=self.metric,
            metric_params=self.metric_params,
            algorithm=self.algorithm,
            leaf_size=self.leaf_size,
            p=self.p,
            n_jobs=self.n_jobs
        )
        
        self.labels_ = self.model.fit_predict(X)
        
        # Store relevant attributes
        self.n_features_in_ = X.shape[1]
        
        self.is_fitted = True
        return self
    
    def get_params(self) -> Dict[str, Any]:
        """Get parameters for this estimator."""
        return {
            'eps': self.eps,
            'min_samples': self.min_samples,
            'metric': self.metric,
            'metric_params': self.metric_params,
            'algorithm': self.algorithm,
            'leaf_size': self.leaf_size,
            'p': self.p,
            'n_jobs': self.n_jobs,
            'store_training_data': self.store_training_data
        }
    
    def set_params(self, **params) -> 'DBSCANClusterer':
        """Set the parameters of this estimator."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
    
    def plot_clusters(self, 
                     X: Optional[np.ndarray] = None,
                     title: str = "DBSCAN Clustering",
                     figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Create a visualization of the clustered data.
        
        Args:
            X: Data to plot. If None, uses stored training data.
            title: Title for the plot
            figsize: Size of the figure (width, height) in inches
            
        Returns:
            matplotlib Figure object
            
        Raises:
            ValueError: If no data is available to plot
            NotFittedError: If the model isn't fitted
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before plot_clusters()")
        
        # Determine which data to plot
        if X is None:
            if self.X_train is None:
                raise ValueError("No data available to plot. Either provide X or initialize with store_training_data=True")
            X = self.X_train
        
        self._validate_data(X)
        
        # Get labels for the data we're plotting
        labels = self.labels_ if X is self.X_train else self.model.fit_predict(X)
        
        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot all points colored by cluster
        unique_labels = np.unique(labels)
        colors = plt.cm.viridis(np.linspace(0, 1, len(unique_labels)))
        
        for k, col in zip(unique_labels, colors):
            if k == -1:
                # Black used for noise
                col = [0, 0, 0, 1]
            
            class_member_mask = (labels == k)
            
            ax.scatter(
                X[class_member_mask, 0],
                X[class_member_mask, 1],
                s=30,
                c=[col],
                edgecolor='k',
                alpha=0.8,
                label=f'Cluster {k}' if k != -1 else 'Noise'
            )
        
        ax.set_xlabel("Feature 1")
        ax.set_ylabel("Feature 2")
        ax.set_title(f"{title} (eps={self.eps}, min_samples={self.min_samples})")
        ax.legend(loc="best")
        
        plt.tight_layout()
        return fig
    
    def evaluate(self, X: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Evaluate clustering performance using standard metrics.
        
        Args:
            X: Data to evaluate, shape (n_samples, n_features). 
               If None, uses training data.
            
        Returns:
            Dictionary of evaluation metrics
            
        Raises:
            NotFittedError: If the model isn't fitted
            ValueError: If evaluation is not possible
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before evaluate()")
        
        if X is None:
            if self.X_train is None:
                raise ValueError("No data available for evaluation")
            X = self.X_train
        
        self._validate_data(X)
        
        labels = self.labels_ if X is self.X_train else self.model.fit_predict(X)
        
        # Filter out noise points for metrics that require multiple clusters
        non_noise_mask = (labels != -1)
        X_non_noise = X[non_noise_mask]
        labels_non_noise = labels[non_noise_mask]
        
        metrics = {}
        
        # Only calculate metrics if we have at least 2 clusters (excluding noise)
        unique_clusters = np.unique(labels_non_noise)
        if len(unique_clusters) > 1:
            metrics['silhouette_score'] = silhouette_score(X_non_noise, labels_non_noise)
            metrics['davies_bouldin_score'] = davies_bouldin_score(X_non_noise, labels_non_noise)
        
        # Count clusters and noise points
        metrics['n_clusters'] = len(unique_clusters)
        metrics['n_noise_points'] = np.sum(labels == -1)
        metrics['noise_ratio'] = metrics['n_noise_points'] / len(labels)
        
        return metrics
    
    def _validate_data(self, X: np.ndarray) -> None:
        """Validate input data format and content."""
        if not isinstance(X, np.ndarray):
            raise ValueError(f"Expected numpy array, got {type(X)}")
        
        if X.ndim != 2:
            raise ValueError(f"Expected 2D array, got {X.ndim}D array")
        
        if np.isnan(X).any() or np.isinf(X).any():
            raise ValueError("Input contains NaN or infinity values")
        
        # For visualization, we need at least 2 features
        if X.shape[1] < 2 and self.store_training_data:
            raise ValueError("At least 2 features required for visualization")
    
    def tune_parameters(self, 
                      X: np.ndarray,
                      eps_range: np.ndarray = np.linspace(0.1, 2.0, 20),
                      min_samples_range: range = range(2, 21, 2),
                      metric: str = 'silhouette',
                      cv_folds: int = 3) -> Dict[str, Any]:
        """
        Perform hyperparameter tuning for DBSCAN clustering.
        
        Args:
            X: Data to tune on, shape (n_samples, n_features)
            eps_range: Array of eps values to try
            min_samples_range: Range of min_samples values to try
            metric: Evaluation metric to optimize ('silhouette', 'davies_bouldin')
            cv_folds: Number of cross-validation folds (not used for DBSCAN but kept for API consistency)
            
        Returns:
            Dictionary containing best parameters and evaluation results
        """
        self._validate_data(X)
        
        if X.shape[0] < 10:
            raise ValueError("Not enough samples for meaningful hyperparameter tuning")
        
        # Standardize data for consistent clustering
        X_scaled = StandardScaler().fit_transform(X)
        
        results = []
        best_score = -float('inf') if metric in ['silhouette'] else float('inf')
        best_params = None
        
        for eps in eps_range:
            for min_samples in min_samples_range:
                try:
                    model = SKDBSCAN(
                        eps=eps,
                        min_samples=min_samples,
                        metric=self.metric,
                        algorithm=self.algorithm,
                        leaf_size=self.leaf_size,
                        p=self.p,
                        n_jobs=self.n_jobs
                    )
                    labels = model.fit_predict(X_scaled)
                    
                    # Filter out noise points
                    non_noise_mask = (labels != -1)
                    X_non_noise = X_scaled[non_noise_mask]
                    labels_non_noise = labels[non_noise_mask]
                    
                    # Skip if not enough clusters for metrics
                    if len(np.unique(labels_non_noise)) < 2:
                        continue
                    
                    # Calculate the requested metric
                    if metric == 'silhouette':
                        score = silhouette_score(X_non_noise, labels_non_noise)
                        is_better = (score > best_score)
                    elif metric == 'davies_bouldin':
                        score = davies_bouldin_score(X_non_noise, labels_non_noise)
                        is_better = (score < best_score)
                    else:
                        raise ValueError(f"Unknown metric: {metric}")
                    
                    results.append({
                        'eps': eps,
                        'min_samples': min_samples,
                        'score': score
                    })
                    
                    if is_better:
                        best_score = score
                        best_params = {'eps': eps, 'min_samples': min_samples}
                        
                except Exception as e:
                    warnings.warn(f"Failed to evaluate eps={eps}, min_samples={min_samples}: {str(e)}")
                    continue
        
        # Update model with best parameters if found
        if best_params:
            self.eps = best_params['eps']
            self.min_samples = best_params['min_samples']
            self.fit(X_scaled)
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'metric_used': metric,
            'all_results': results
        }
    
    def plot_tuning_results(self, 
                           tuning_results: Dict[str, Any],
                           figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Visualize hyperparameter tuning results for DBSCAN.
        
        Args:
            tuning_results: Results from tune_parameters()
            figsize: Size of the figure
            
        Returns:
            matplotlib Figure object
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Extract data for plotting
        eps_vals = [r['eps'] for r in tuning_results['all_results']]
        min_samples_vals = [r['min_samples'] for r in tuning_results['all_results']]
        scores = [r['score'] for r in tuning_results['all_results']]
        
        # Scatter plot of parameter combinations
        scatter = ax1.scatter(
            eps_vals, 
            min_samples_vals, 
            c=scores,
            cmap='viridis',
            s=100,
            edgecolor='k'
        )
        
        # Highlight best parameters
        if tuning_results['best_params']:
            ax1.scatter(
                tuning_results['best_params']['eps'],
                tuning_results['best_params']['min_samples'],
                s=200,
                c='red',
                marker='*',
                edgecolor='black',
                label='Best Parameters'
            )
        
        ax1.set_xlabel('eps')
        ax1.set_ylabel('min_samples')
        ax1.set_title(f'Parameter Search ({tuning_results["metric_used"]} score)')
        fig.colorbar(scatter, ax=ax1, label=tuning_results['metric_used'].replace('_', ' ').title())
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.legend()
        
        # Heatmap of results (pivot by eps and min_samples)
        param_df = pd.DataFrame(tuning_results['all_results'])
        pivot_table = param_df.pivot_table(
            index='eps', 
            columns='min_samples', 
            values='score',
            aggfunc='mean'
        )
        
        heatmap = ax2.imshow(
            pivot_table, 
            cmap='viridis',
            aspect='auto',
            interpolation='nearest'
        )
        
        fig.colorbar(heatmap, ax=ax2, label=tuning_results['metric_used'].replace('_', ' ').title())
        
        ax2.set_xticks(np.arange(len(pivot_table.columns)))
        ax2.set_yticks(np.arange(len(pivot_table.index)))
        ax2.set_xticklabels([f"{c:.2f}" for c in pivot_table.columns])
        ax2.set_yticklabels([f"{c:.2f}" for c in pivot_table.index])
        ax2.set_xlabel('min_samples')
        ax2.set_ylabel('eps')
        ax2.set_title('Parameter Heatmap')
        
        # Add text annotations with scores
        for i in range(len(pivot_table.index)):
            for j in range(len(pivot_table.columns)):
                if not np.isnan(pivot_table.iloc[i, j]):
                    ax2.text(j, i, f"{pivot_table.iloc[i, j]:.3f}",
                             ha="center", va="center", color="w")
        
        plt.tight_layout()
        return fig

class SpectralClusteringClusterer:
    """Production-ready implementation of Spectral Clustering algorithm.
    
    This class provides a robust implementation of Spectral Clustering with:
    - Comprehensive parameter validation
    - Detailed documentation
    - Configurable parameters
    - Support for different affinity metrics
    - Evaluation metrics
    - Visualization capabilities
    
    Example:
        clusterer = SpectralClusteringClusterer(n_clusters=3)
        clusterer.fit(data)
        labels = clusterer.labels_
        fig = clusterer.plot_clusters()
    """
    
    def __init__(self,
                 n_clusters: int = 8,
                 eigen_solver: Optional[str] = None,
                 n_components: Optional[int] = None,
                 random_state: Optional[int] = None,
                 n_init: int = 10,
                 gamma: float = 1.0,
                 affinity: str = 'rbf',
                 n_neighbors: int = 10,
                 eigen_tol: float = 0.0,
                 assign_labels: str = 'kmeans',
                 degree: int = 3,
                 coef0: float = 1,
                 kernel_params: Optional[Dict] = None,
                 n_jobs: Optional[int] = None,
                 store_training_data: bool = False):
        """
        Initialize the Spectral Clustering clusterer with specified parameters.
        
        Args:
            n_clusters: The dimension of the projection subspace
            eigen_solver: The eigenvalue decomposition strategy to use
            n_components: Number of eigenvectors to use for the spectral embedding
            random_state: Random seed for reproducibility
            n_init: Number of times the k-means algorithm will be run
            gamma: Kernel coefficient for rbf, poly, sigmoid, laplacian kernels
            affinity: How to construct the affinity matrix ('rbf', 'nearest_neighbors', 
                     'precomputed', 'precomputed_nearest_neighbors', or a callable)
            n_neighbors: Number of neighbors for k-neighbor affinity
            eigen_tol: Stopping criterion for eigendecomposition
            assign_labels: Strategy to assign labels in the embedding space ('kmeans' or 'discretize')
            degree: Degree for poly kernels
            coef0: Zero coefficient for poly and sigmoid kernels
            kernel_params: Parameters for kernels
            n_jobs: The number of parallel jobs to run
            store_training_data: Whether to store training data for visualization
        """
        # Validate parameters
        if n_clusters <= 0:
            raise ValueError("n_clusters must be positive")
        if n_init <= 0:
            raise ValueError("n_init must be positive")
        if gamma <= 0:
            raise ValueError("gamma must be positive")
        if n_neighbors <= 0:
            raise ValueError("n_neighbors must be positive")
        if degree <= 0:
            raise ValueError("degree must be positive")
        if coef0 < 0:
            raise ValueError("coef0 must be non-negative")
        if eigen_tol < 0:
            raise ValueError("eigen_tol must be non-negative")
            
        # Validate string parameters
        valid_eigen_solvers = [None, 'arpack', 'lobpcg', 'amg']
        if eigen_solver not in valid_eigen_solvers:
            raise ValueError(f"eigen_solver must be one of {valid_eigen_solvers}")
            
        valid_affinities = ['rbf', 'nearest_neighbors', 'precomputed', 
                           'precomputed_nearest_neighbors']
        if affinity not in valid_affinities and not callable(affinity):
            raise ValueError(f"affinity must be one of {valid_affinities} or a callable")
            
        valid_assign_labels = ['kmeans', 'discretize']
        if assign_labels not in valid_assign_labels:
            raise ValueError(f"assign_labels must be one of {valid_assign_labels}")
        
        self.n_clusters = n_clusters
        self.eigen_solver = eigen_solver
        self.n_components = n_components
        self.random_state = random_state
        self.n_init = n_init
        self.gamma = gamma
        self.affinity = affinity
        self.n_neighbors = n_neighbors
        self.eigen_tol = eigen_tol
        self.assign_labels = assign_labels
        self.degree = degree
        self.coef0 = coef0
        self.kernel_params = kernel_params
        self.n_jobs = n_jobs
        self.store_training_data = store_training_data
        self.model = None
        self.is_fitted = False
        self.X_train = None
        self.labels_ = None
        self.affinity_matrix_ = None
        self.n_features_in_ = None
    
    def fit(self, X: np.ndarray) -> 'SpectralClusteringClusterer':
        """
        Perform Spectral Clustering.
        
        Args:
            X: Training instances to cluster, shape (n_samples, n_features)
            
        Returns:
            self: The fitted clusterer
            
        Raises:
            ValueError: If input data is invalid
        """
        # Input validation
        self._validate_data(X)
        
        # Store training data if requested
        if self.store_training_data:
            self.X_train = X.copy()
        
        # Create and fit the model
        self.model = SKSpecClust(
            n_clusters=self.n_clusters,
            eigen_solver=self.eigen_solver,
            n_components=self.n_components,
            random_state=self.random_state,
            n_init=self.n_init,
            gamma=self.gamma,
            affinity=self.affinity,
            n_neighbors=self.n_neighbors,
            eigen_tol=self.eigen_tol,
            assign_labels=self.assign_labels,
            degree=self.degree,
            coef0=self.coef0,
            kernel_params=self.kernel_params,
            n_jobs=self.n_jobs
        )
        
        self.labels_ = self.model.fit_predict(X)
        
        # Store relevant attributes
        self.n_features_in_ = X.shape[1]
        
        self.is_fitted = True
        return self
    
    def get_params(self) -> Dict[str, Any]:
        """Get parameters for this estimator."""
        return {
            'n_clusters': self.n_clusters,
            'eigen_solver': self.eigen_solver,
            'n_components': self.n_components,
            'random_state': self.random_state,
            'n_init': self.n_init,
            'gamma': self.gamma,
            'affinity': self.affinity,
            'n_neighbors': self.n_neighbors,
            'eigen_tol': self.eigen_tol,
            'assign_labels': self.assign_labels,
            'degree': self.degree,
            'coef0': self.coef0,
            'kernel_params': self.kernel_params,
            'n_jobs': self.n_jobs,
            'store_training_data': self.store_training_data
        }
    
    def set_params(self, **params) -> 'SpectralClusteringClusterer':
        """Set the parameters of this estimator."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
    
    def plot_clusters(self, 
                     X: Optional[np.ndarray] = None,
                     title: str = "Spectral Clustering",
                     figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Create a visualization of the clustered data.
        
        Args:
            X: Data to plot. If None, uses stored training data.
            title: Title for the plot
            figsize: Size of the figure (width, height) in inches
            
        Returns:
            matplotlib Figure object
            
        Raises:
            ValueError: If no data is available to plot
            NotFittedError: If the model isn't fitted
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before plot_clusters()")
        
        # Determine which data to plot
        if X is None:
            if self.X_train is None:
                raise ValueError("No data available to plot. Either provide X or initialize with store_training_data=True")
            X = self.X_train
        
        self._validate_data(X)
        
        # Get labels for the data we're plotting
        labels = self.labels_ if X is self.X_train else self.model.fit_predict(X)
        
        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot all points colored by cluster
        unique_labels = np.unique(labels)
        colors = plt.cm.viridis(np.linspace(0, 1, len(unique_labels)))
        
        for k, col in zip(unique_labels, colors):
            class_member_mask = (labels == k)
            
            ax.scatter(
                X[class_member_mask, 0],
                X[class_member_mask, 1],
                s=30,
                c=[col],
                edgecolor='k',
                alpha=0.8,
                label=f'Cluster {k}'
            )
        
        ax.set_xlabel("Feature 1")
        ax.set_ylabel("Feature 2")
        ax.set_title(f"{title} (n_clusters={self.n_clusters})")
        ax.legend(loc="best")
        
        plt.tight_layout()
        return fig
    
    def evaluate(self, X: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Evaluate clustering performance using standard metrics.
        
        Args:
            X: Data to evaluate, shape (n_samples, n_features). 
               If None, uses training data.
            
        Returns:
            Dictionary of evaluation metrics
            
        Raises:
            NotFittedError: If the model isn't fitted
            ValueError: If evaluation is not possible
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before evaluate()")
        
        if X is None:
            if self.X_train is None:
                raise ValueError("No data available for evaluation")
            X = self.X_train
        
        self._validate_data(X)
        
        labels = self.labels_ if X is self.X_train else self.model.fit_predict(X)
        
        # Evaluate metrics
        metrics = {}
        unique_clusters = np.unique(labels)
        
        # Only calculate metrics if we have at least 2 clusters
        if len(unique_clusters) > 1:
            metrics['silhouette_score'] = silhouette_score(X, labels)
            metrics['davies_bouldin_score'] = davies_bouldin_score(X, labels)
        
        metrics['n_clusters'] = len(unique_clusters)
        
        return metrics
    
    def _validate_data(self, X: np.ndarray) -> None:
        """Validate input data format and content."""
        if not isinstance(X, np.ndarray):
            raise ValueError(f"Expected numpy array, got {type(X)}")
        
        if X.ndim != 2:
            raise ValueError(f"Expected 2D array, got {X.ndim}D array")
        
        if np.isnan(X).any() or np.isinf(X).any():
            raise ValueError("Input contains NaN or infinity values")
        
        # For visualization, we need at least 2 features
        if X.shape[1] < 2 and self.store_training_data:
            raise ValueError("At least 2 features required for visualization")
    
    def tune_parameters(self, 
                      X: np.ndarray,
                      n_clusters_range: range = range(2, 11),
                      affinity_options: List[str] = ['rbf', 'nearest_neighbors'],
                      n_neighbors_range: range = range(5, 21, 5),
                      metric: str = 'silhouette',
                      cv_folds: int = 3) -> Dict[str, Any]:
        """
        Perform hyperparameter tuning for Spectral Clustering.
        
        Args:
            X: Data to tune on, shape (n_samples, n_features)
            n_clusters_range: Range of n_clusters values to try
            affinity_options: List of affinity metrics to try
            n_neighbors_range: Range of n_neighbors values (for 'nearest_neighbors' affinity)
            metric: Evaluation metric to optimize ('silhouette', 'davies_bouldin')
            cv_folds: Number of cross-validation folds
            
        Returns:
            Dictionary containing best parameters and evaluation results
        """
        self._validate_data(X)
        
        if X.shape[0] < 10:
            raise ValueError("Not enough samples for meaningful hyperparameter tuning")
        
        # Standardize data for consistent clustering
        X_scaled = StandardScaler().fit_transform(X)
        
        results = []
        best_score = -float('inf') if metric in ['silhouette'] else float('inf')
        best_params = None
        
        for n_clusters in n_clusters_range:
            for affinity in affinity_options:
                # Skip if n_clusters is too large
                if n_clusters >= X.shape[0]:
                    continue
                
                # Only use n_neighbors with nearest_neighbors affinity
                if affinity == 'nearest_neighbors':
                    for n_neighbors in n_neighbors_range:
                        try:
                            model = SKSpecClust(
                                n_clusters=n_clusters,
                                affinity=affinity,
                                n_neighbors=n_neighbors,
                                random_state=self.random_state,
                                n_init=self.n_init
                            )
                            labels = model.fit_predict(X_scaled)
                            
                            # Skip if all points are in one cluster
                            if len(np.unique(labels)) < 2:
                                continue
                                
                            # Calculate the requested metric
                            if metric == 'silhouette':
                                score = silhouette_score(X_scaled, labels)
                                is_better = (score > best_score)
                            elif metric == 'davies_bouldin':
                                score = davies_bouldin_score(X_scaled, labels)
                                is_better = (score < best_score)
                            else:
                                raise ValueError(f"Unknown metric: {metric}")
                            
                            results.append({
                                'n_clusters': n_clusters,
                                'affinity': affinity,
                                'n_neighbors': n_neighbors,
                                'score': score
                            })
                            
                            if is_better:
                                best_score = score
                                best_params = {
                                    'n_clusters': n_clusters,
                                    'affinity': affinity,
                                    'n_neighbors': n_neighbors
                                }
                                
                        except Exception as e:
                            warnings.warn(f"Failed to evaluate n_clusters={n_clusters}, affinity={affinity}, n_neighbors={n_neighbors}: {str(e)}")
                            continue
                else:
                    # For other affinity types (like 'rbf')
                    try:
                        model = SKSpecClust(
                            n_clusters=n_clusters,
                            affinity=affinity,
                            random_state=self.random_state,
                            n_init=self.n_init
                        )
                        labels = model.fit_predict(X_scaled)
                        
                        # Skip if all points are in one cluster
                        if len(np.unique(labels)) < 2:
                            continue
                            
                        # Calculate the requested metric
                        if metric == 'silhouette':
                            score = silhouette_score(X_scaled, labels)
                            is_better = (score > best_score)
                        elif metric == 'davies_bouldin':
                            score = davies_bouldin_score(X_scaled, labels)
                            is_better = (score < best_score)
                        else:
                            raise ValueError(f"Unknown metric: {metric}")
                        
                        results.append({
                            'n_clusters': n_clusters,
                            'affinity': affinity,
                            'n_neighbors': None,
                            'score': score
                        })
                        
                        if is_better:
                            best_score = score
                            best_params = {
                                'n_clusters': n_clusters,
                                'affinity': affinity,
                                'n_neighbors': None
                            }
                            
                    except Exception as e:
                        warnings.warn(f"Failed to evaluate n_clusters={n_clusters}, affinity={affinity}: {str(e)}")
                        continue
        
        # Update model with best parameters if found
        if best_params:
            self.n_clusters = best_params['n_clusters']
            self.affinity = best_params['affinity']
            if 'n_neighbors' in best_params and best_params['n_neighbors'] is not None:
                self.n_neighbors = best_params['n_neighbors']
            self.fit(X_scaled)
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'metric_used': metric,
            'all_results': results
        }
    
    def plot_tuning_results(self, 
                           tuning_results: Dict[str, Any],
                           figsize: Tuple[int, int] = (12, 8)) -> plt.Figure:
        """
        Visualize hyperparameter tuning results for Spectral Clustering.
        
        Args:
            tuning_results: Results from tune_parameters()
            figsize: Size of the figure
            
        Returns:
            matplotlib Figure object
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Extract data for plotting
        n_clusters_vals = [r['n_clusters'] for r in tuning_results['all_results']]
        affinity_vals = [r['affinity'] for r in tuning_results['all_results']]
        n_neighbors_vals = [r['n_neighbors'] for r in tuning_results['all_results']]
        scores = [r['score'] for r in tuning_results['all_results']]
        
        # Map affinity types to numeric values for plotting
        affinity_map = {aff: i for i, aff in enumerate(set(affinity_vals))}
        affinity_numeric = [affinity_map[aff] for aff in affinity_vals]
        
        # Scatter plot of parameter combinations
        scatter = ax1.scatter(
            n_clusters_vals, 
            affinity_numeric, 
            c=scores,
            s=[50 if n is None else 100 for n in n_neighbors_vals],  # Different size for n_neighbors
            cmap='viridis',
            edgecolor='k'
        )
        
        # Highlight best parameters
        if tuning_results['best_params']:
            best_affinity_idx = affinity_map[tuning_results['best_params']['affinity']]
            best_n_neighbors = tuning_results['best_params'].get('n_neighbors')
            
            ax1.scatter(
                tuning_results['best_params']['n_clusters'],
                best_affinity_idx,
                s=200,
                c='red',
                marker='*',
                edgecolor='black',
                label='Best Parameters'
            )
        
        ax1.set_xlabel('n_clusters')
        ax1.set_ylabel('Affinity Type')
        ax1.set_yticks(list(affinity_map.values()))
        ax1.set_yticklabels(list(affinity_map.keys()))
        ax1.set_title(f'Parameter Search ({tuning_results["metric_used"]} score)')
        fig.colorbar(scatter, ax=ax1, label=tuning_results['metric_used'].replace('_', ' ').title())
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.legend()
        
        # Heatmap of results (pivot by n_clusters and affinity)
        param_df = pd.DataFrame(tuning_results['all_results'])
        
        # Filter out None values for n_neighbors
        param_df = param_df[param_df['n_neighbors'].notnull()]
        
        if not param_df.empty:
            pivot_table = param_df.pivot_table(
                index='n_clusters', 
                columns='n_neighbors', 
                values='score',
                aggfunc='mean'
            )
            
            heatmap = ax2.imshow(
                pivot_table, 
                cmap='viridis',
                aspect='auto',
                interpolation='nearest'
            )
            
            fig.colorbar(heatmap, ax=ax2, label=tuning_results['metric_used'].replace('_', ' ').title())
            
            ax2.set_xticks(np.arange(len(pivot_table.columns)))
            ax2.set_yticks(np.arange(len(pivot_table.index)))
            ax2.set_xticklabels([f"{int(c)}" for c in pivot_table.columns])
            ax2.set_yticklabels([f"{int(c)}" for c in pivot_table.index])
            ax2.set_xlabel('n_neighbors')
            ax2.set_ylabel('n_clusters')
            ax2.set_title('Parameter Heatmap')
            
            # Add text annotations with scores
            for i in range(len(pivot_table.index)):
                for j in range(len(pivot_table.columns)):
                    if not np.isnan(pivot_table.iloc[i, j]):
                        ax2.text(j, i, f"{pivot_table.iloc[i, j]:.3f}",
                                 ha="center", va="center", color="w")
        else:
            ax2.text(0.5, 0.5, 'No valid parameter combinations\nfor heatmap visualization',
                    ha='center', va='center', fontsize=12)
            ax2.set_axis_off()
        
        plt.tight_layout()
        return fig


class ClusteringModel:
    """Unified interface for multiple clustering algorithms.
    
    This class provides a consistent API to work with different clustering algorithms,
    making it easy to switch between them in a machine learning pipeline.
    
    Supported algorithms:
    - 'kmeans': K-Means clustering
    - 'dbscan': DBSCAN clustering
    - 'spectral': Spectral Clustering
    
    Example:
        # Create a K-Means model
        model = ClusteringModel(algorithm='kmeans', n_clusters=3)
        model.fit(data)
        labels = model.predict(data)
        
        # Switch to Spectral Clustering without changing the API
        model = ClusteringModel(algorithm='spectral', n_clusters=3)
        model.fit(data)
        labels = model.predict(data)
    """
    
    def __init__(self, algorithm: str = 'kmeans', **kwargs):
        """
        Initialize the clustering model with specified algorithm and parameters.
        
        Args:
            algorithm: The clustering algorithm to use ('kmeans', 'dbscan', or 'spectral')
            **kwargs: Algorithm-specific parameters
        """
        self.algorithm = algorithm.lower()
        self.model = None
        self.is_fitted = False
        
        # Initialize the appropriate model
        if self.algorithm == 'kmeans':
            self.model = KMeansClusterer(**kwargs)
        elif self.algorithm == 'dbscan':
            self.model = DBSCANClusterer(**kwargs)
        elif self.algorithm == 'spectral':
            self.model = SpectralClusteringClusterer(**kwargs)
        else:
            raise ValueError(f"Unknown clustering algorithm: {algorithm}. "
                            f"Supported algorithms: 'kmeans', 'dbscan', 'spectral'")
    
    def fit(self, X: np.ndarray) -> 'ClusteringModel':
        """
        Fit the clustering model to the data.
        
        Args:
            X: Training data, shape (n_samples, n_features)
            
        Returns:
            self: The fitted model
        """
        self.model.fit(X)
        self.is_fitted = True
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict cluster labels for new data.
        
        Args:
            X: New data to predict, shape (n_samples, n_features)
            
        Returns:
            Cluster labels
            
        Raises:
            NotFittedError: If the model isn't fitted
        """
        if not self.is_fitted:
            raise NotFittedError("Call fit() before predict()")
        
        # DBSCAN and Spectral Clustering don't have a separate predict method
        if self.algorithm in ['dbscan', 'spectral']:
            return self.model.fit_predict(X)
        else:
            return self.model.predict(X)
    
    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """
        Fit the model and predict cluster labels.
        
        Args:
            X: Training data, shape (n_samples, n_features)
            
        Returns:
            Cluster labels
        """
        return self.fit(X).predict(X)
    
    def plot_clusters(self, 
                     X: Optional[np.ndarray] = None,
                     title: Optional[str] = None,
                     figsize: Tuple[int, int] = (10, 8)) -> plt.Figure:
        """
        Create a visualization of the clustered data.
        
        Args:
            X: Data to plot. If None, uses stored training data.
            title: Title for the plot. If None, uses a default title.
            figsize: Size of the figure (width, height) in inches
            
        Returns:
            matplotlib Figure object
        """
        if title is None:
            title = f"{self.algorithm.upper()} Clustering"
        
        return self.model.plot_clusters(X, title, figsize)
    
    def evaluate(self, X: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Evaluate clustering performance using standard metrics.
        
        Args:
            X: Data to evaluate. If None, uses training data.
            
        Returns:
            Dictionary of evaluation metrics
        """
        return self.model.evaluate(X)
    
    def get_params(self) -> Dict[str, Any]:
        """Get parameters for this estimator."""
        return self.model.get_params()
    
    def set_params(self, **params) -> 'ClusteringModel':
        """Set the parameters of this estimator."""
        self.model.set_params(**params)
        return self
    
    def tune_parameters(self, 
                      X: np.ndarray,
                      **kwargs) -> Dict[str, Any]:
        """
        Tune hyperparameters for the clustering algorithm.
        
        Args:
            X: Data to tune on
            **kwargs: Algorithm-specific tuning parameters
            
        Returns:
            Dictionary containing best parameters and evaluation results
        """
        return self.model.tune_parameters(X, **kwargs)
    
    def plot_tuning_results(self, 
                           tuning_results: Dict[str, Any],
                           figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Visualize hyperparameter tuning results.
        
        Args:
            tuning_results: Results from tune_parameters()
            figsize: Size of the figure
            
        Returns:
            matplotlib Figure object
        """
        return self.model.plot_tuning_results(tuning_results, figsize)
    
    @property
    def labels_(self) -> np.ndarray:
        """Cluster labels of each point in the training data."""
        if not self.is_fitted:
            raise NotFittedError("Call fit() before accessing labels_")
        return self.model.labels_
    
    @property
    def n_clusters_(self) -> int:
        """Number of clusters found by the algorithm."""
        if not self.is_fitted:
            raise NotFittedError("Call fit() before accessing n_clusters_")
        
        # Count unique clusters
        unique_labels = np.unique(self.model.labels_)
        return len(unique_labels)


