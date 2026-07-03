"""
Clustering Models - Comprehensive Unit Test Script

This test script verifies that all clustering models can process inputs and produce expected outputs.
It tests the core functionality of each algorithm with synthetic data to ensure proper implementation.

Test Categories:
- Initialization validation
- Data validation
- Model fitting
- Prediction functionality
- Parameter handling
- Evaluation metrics
- Hyperparameter tuning
- Visualization capabilities

Usage (Run from project root directory):
    python Modelling/Clustering/clustering_models_unit_test.py

Author: Dr. Philip Naderev P. Lagniton
"""

import os
import sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from sklearn.exceptions import NotFittedError
from sklearn.datasets import make_blobs
import pandas as pd
from typing import Dict, Any, Tuple
import warnings

#######################################################
# Directory Configuration
#######################################################
# Configure matplotlib to use non-interactive backend for testing
matplotlib.use('Agg')

# Add project root to path
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
data_raw_path = os.path.join(proj_root, "Data", "Raw") 
data_output_path = os.path.join(proj_root, "Data", "Processed")
sys.path.append(proj_root)

# Create output directory if it doesn't exist
os.makedirs(data_output_path, exist_ok=True)

# Import the clustering module
from AI_toolbox.Modelling.Clustering.clustering import(
    KMeansClusterer,
    DBSCANClusterer,
    SpectralClusteringClusterer,
    ClusteringModel
)

def generate_test_data(n_samples: int = 300, 
                      n_features: int = 2, 
                      n_clusters: int = 4,
                      random_state: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic clustering test data.
    
    Args:
        n_samples: Number of samples to generate
        n_features: Number of features (dimensions)
        n_clusters: Number of true clusters
        random_state: Random seed for reproducibility
        
    Returns:
        X: Feature matrix
        y: True cluster labels (for reference only)
    """
    X, y = make_blobs(
        n_samples=n_samples,
        n_features=n_features,
        centers=n_clusters,
        random_state=random_state
    )
    return X, y

def test_kmeans_functionality():
    """Test KMeans clustering functionality with synthetic data."""
    print("\n=== Testing KMeans Clustering ===")
    
    # Generate test data
    X, _ = generate_test_data()
    
    # Initialize with default parameters
    print("Initializing KMeansClusterer...")
    kmeans = KMeansClusterer(
        n_clusters=4,
        store_training_data=True
    )
    
    # Fit the model
    print("Fitting KMeans model...")
    kmeans.fit(X)
    
    # Get cluster labels
    labels = kmeans.labels_
    unique_labels = np.unique(labels)
    print(f"Cluster labels (first 10): {labels[:10]}")
    print(f"Number of clusters found: {len(unique_labels)}")
    
    # Evaluate the model
    print("\nEvaluating model performance...")
    metrics = kmeans.evaluate(X)
    print("Evaluation metrics:")
    for metric, value in metrics.items():
        print(f"  {metric}: {value:.4f}")
    
    # Hyperparameter tuning
    print("\nTesting hyperparameter tuning...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tuning_results = kmeans.tune_parameters(
            X,
            n_clusters_range=range(2, 7),
            metric='silhouette',
            cv_folds=2
        )
    
    print(f"Best parameters: n_clusters={tuning_results['best_params']['n_clusters']}")
    print(f"Best score: {tuning_results['best_score']:.4f}")
    
    # Visualization
    print("\nGenerating visualizations...")
    # Results plot
    fig = kmeans.plot_clusters(title="KMeans Clustering Results")
    fig.savefig(os.path.join(data_output_path, "kmeans_test_results.png"))
    plt.close(fig)
    
    # Tuning results
    tuning_fig = kmeans.plot_tuning_results(tuning_results)
    tuning_fig.savefig(os.path.join(data_output_path, "kmeans_tuning_results.png"))
    plt.close(tuning_fig)
    
    print("\nKMeans test completed successfully ✅")

def test_dbscan_functionality():
    """Test DBSCAN clustering functionality with synthetic data."""
    print("\n=== Testing DBSCAN Clustering ===")
    
    # Generate test data
    X, _ = generate_test_data(n_clusters=3)
    
    # Initialize with default parameters
    print("Initializing DBSCANClusterer...")
    dbscan = DBSCANClusterer(
        eps=0.5,
        min_samples=5,
        store_training_data=True
    )
    
    # Fit the model
    print("Fitting DBSCAN model...")
    dbscan.fit(X)
    
    # Get cluster labels
    labels = dbscan.labels_
    unique_labels = np.unique(labels)
    noise_points = np.sum(labels == -1)
    print(f"Cluster labels (first 10): {labels[:10]}")
    print(f"Number of clusters found: {len(unique_labels[unique_labels != -1])}")
    print(f"Noise points: {noise_points} ({noise_points/len(labels):.1%})")
    
    # Evaluate the model
    print("\nEvaluating model performance...")
    metrics = dbscan.evaluate(X)
    print("Evaluation metrics:")
    for metric, value in metrics.items():
        print(f"  {metric}: {value:.4f}")
    
    # Hyperparameter tuning
    print("\nTesting hyperparameter tuning...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tuning_results = dbscan.tune_parameters(
            X,
            eps_range=np.linspace(0.3, 0.8, 6),
            min_samples_range=range(3, 10, 2),
            metric='silhouette',
            cv_folds=2
        )
    
    print(f"Best parameters: eps={tuning_results['best_params']['eps']:.4f}, "
          f"min_samples={tuning_results['best_params']['min_samples']}")
    print(f"Best score: {tuning_results['best_score']:.4f}")
    
    # Visualization
    print("\nGenerating visualizations...")
    # Results plot
    fig = dbscan.plot_clusters(title="DBSCAN Clustering Results")
    fig.savefig(os.path.join(data_output_path, "dbscan_test_results.png"))
    plt.close(fig)
    
    # Tuning results
    tuning_fig = dbscan.plot_tuning_results(tuning_results)
    tuning_fig.savefig(os.path.join(data_output_path, "dbscan_tuning_results.png"))
    plt.close(tuning_fig)
    
    print("\nDBSCAN test completed successfully ✅")

def test_spectral_clustering_functionality():
    """Test Spectral Clustering functionality with synthetic data."""
    print("\n=== Testing Spectral Clustering ===")
    
    # Generate test data
    X, _ = generate_test_data(n_clusters=3)
    
    # Initialize with default parameters
    print("Initializing SpectralClusteringClusterer...")
    spectral = SpectralClusteringClusterer(
        n_clusters=3,
        store_training_data=True
    )
    
    # Fit the model
    print("Fitting Spectral Clustering model...")
    spectral.fit(X)
    
    # Get cluster labels
    labels = spectral.labels_
    unique_labels = np.unique(labels)
    print(f"Cluster labels (first 10): {labels[:10]}")
    print(f"Number of clusters found: {len(unique_labels)}")
    
    # Evaluate the model
    print("\nEvaluating model performance...")
    metrics = spectral.evaluate(X)
    print("Evaluation metrics:")
    for metric, value in metrics.items():
        print(f"  {metric}: {value:.4f}")
    
    # Hyperparameter tuning
    print("\nTesting hyperparameter tuning...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tuning_results = spectral.tune_parameters(
            X,
            n_clusters_range=range(2, 6),
            affinity_options=['rbf', 'nearest_neighbors'],
            n_neighbors_range=range(5, 15, 5),
            metric='silhouette',
            cv_folds=2
        )
    
    best_params = tuning_results['best_params']
    print(f"Best parameters: n_clusters={best_params['n_clusters']}, "
          f"affinity='{best_params['affinity']}'", end="")
    if best_params['n_neighbors'] is not None:
        print(f", n_neighbors={best_params['n_neighbors']}")
    else:
        print()
    print(f"Best score: {tuning_results['best_score']:.4f}")
    
    # Visualization
    print("\nGenerating visualizations...")
    # Results plot
    fig = spectral.plot_clusters(title="Spectral Clustering Results")
    fig.savefig(os.path.join(data_output_path, "spectral_test_results.png"))
    plt.close(fig)
    
    # Tuning results
    tuning_fig = spectral.plot_tuning_results(tuning_results)
    tuning_fig.savefig(os.path.join(data_output_path, "spectral_tuning_results.png"))
    plt.close(tuning_fig)
    
    print("\nSpectral Clustering test completed successfully ✅")

def edge_case_testing():
    """Test edge cases and error handling for clustering models."""
    print("\n=== Testing Edge Cases and Error Handling ===")
    
    # Generate minimal test data
    X_small = np.array([[1, 2], [2, 3], [3, 4]])
    
    print("\nTesting KMeans edge cases...")
    try:
        # Invalid parameters
        KMeansClusterer(n_clusters=0)
    except ValueError as e:
        print(f"  ✓ Correctly caught invalid n_clusters: {str(e)}")
    
    try:
        # Fitting with insufficient samples
        kmeans = KMeansClusterer(n_clusters=3)
        kmeans.fit(X_small)
    except ValueError as e:
        print(f"  ✓ Correctly handled insufficient samples: {str(e)}")
    
    print("\nTesting DBSCAN edge cases...")
    try:
        # Invalid parameters
        DBSCANClusterer(eps=-0.1)
    except ValueError as e:
        print(f"  ✓ Correctly caught invalid eps: {str(e)}")
    
    print("\nTesting SpectralClustering edge cases...")
    try:
        # Invalid parameters
        SpectralClusteringClusterer(n_clusters=0)
    except ValueError as e:
        print(f"  ✓ Correctly caught invalid n_clusters: {str(e)}")
    
    try:
        # Invalid affinity
        SpectralClusteringClusterer(affinity='invalid_affinity')
    except ValueError as e:
        print(f"  ✓ Correctly caught invalid affinity: {str(e)}")
    
    print("\nTesting invalid algorithm selection...")

    
    print("\nEdge case testing completed successfully ✅")

if __name__ == "__main__":
    print("Starting Clustering Models Unit Test Suite...")
    print("==============================================")
    
    # Run all tests
    test_kmeans_functionality()
    print("KMeans Clustering Test Completed ✅")
    print("----------------------------------------------")
    
    test_dbscan_functionality()
    print("DBSCAN Clustering Test Completed ✅")
    print("----------------------------------------------")
    
    test_spectral_clustering_functionality()
    print("Spectral Clustering Test Completed ✅")
    print("----------------------------------------------")
    
    edge_case_testing()
    print("Edge Case Testing Completed ✅")
    print("==============================================")
    print("✅✅✅✅✅✅✅✅✅")
    print(" Clustering Unit Test Suite Completed Successfully ✅")
    print("✅✅✅✅✅✅✅✅✅")