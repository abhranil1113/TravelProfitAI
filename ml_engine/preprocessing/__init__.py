"""
ml_engine/preprocessing package entrypoint.
Exposes feature schema validation, preprocessing pipelines, and domain feature builders.
"""

from ml_engine.preprocessing.schema_validator import FeatureSchemaValidator
from ml_engine.preprocessing.pipeline import MLPreprocessingPipeline
from ml_engine.preprocessing.encode_categorical import CategoricalNormalizer
from ml_engine.preprocessing.scale_features import NumericScalerValidator
from ml_engine.preprocessing.split_dataset import TemporalEmbargoSplitter
from ml_engine.preprocessing.preprocess_flight import FlightFeaturePreprocessor
from ml_engine.preprocessing.preprocess_hotel import HotelFeaturePreprocessor

__all__ = [
    "FeatureSchemaValidator",
    "MLPreprocessingPipeline",
    "CategoricalNormalizer",
    "NumericScalerValidator",
    "TemporalEmbargoSplitter",
    "FlightFeaturePreprocessor",
    "HotelFeaturePreprocessor",
]
