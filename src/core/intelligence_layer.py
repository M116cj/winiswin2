"""🧠 Intelligence Layer - Orchestrates SMC + ML pipeline"""
import logging

logger = logging.getLogger(__name__)

class IntelligenceLayer:
    """Orchestrates pattern detection and ML inference"""
    def __init__(self, smc_engine, feature_engineer, ml_predictor):
        self.smc_engine = smc_engine
        self.feature_engineer = feature_engineer
        self.ml_predictor = ml_predictor
