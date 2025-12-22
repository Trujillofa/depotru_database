"""
Configuration Management for Business Analyzer
==============================================
Centralized configuration for database connections and application settings.

Environment Variables:
- NCX_FILE_PATH: Path to Navicat connections file (optional)
- DB_HOST: Database host
- DB_PORT: Database port
- DB_USER: Database username
- DB_PASSWORD: Database password
- DB_NAME: Database name
- OUTPUT_DIR: Directory for output reports (default: ~/business_reports)

Security Best Practices:
1. Use .env file for local development (add to .gitignore!)
2. Use environment variables for production
3. Never commit credentials to version control
4. Consider using secret management services (AWS Secrets Manager, Azure Key Vault, etc.)
"""

import os
from pathlib import Path
import logging

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Look for .env file in current directory and parent directories
    load_dotenv()
    logging.info("Loaded configuration from .env file")
except ImportError:
    logging.warning(
        "python-dotenv not installed. Install with: pip install python-dotenv\n"
        "Using environment variables only."
    )


class Config:
    """Application configuration"""

    # Database Configuration
    # Priority: Environment variables > NCX file > defaults
    NCX_FILE_PATH = os.getenv(
        'NCX_FILE_PATH',
        os.path.expanduser('~/Coding_OMARCHY/python_files/connections.ncx')
    )

    # Direct database connection (if not using NCX file)
    DB_HOST = os.getenv('DB_HOST', None)
    DB_PORT = int(os.getenv('DB_PORT', '1433'))
    DB_USER = os.getenv('DB_USER', None)
    DB_PASSWORD = os.getenv('DB_PASSWORD', None)
    DB_NAME = os.getenv('DB_NAME', 'SmartBusiness')
    DB_TABLE = os.getenv('DB_TABLE', 'banco_datos')

    # Database connection settings
    DB_LOGIN_TIMEOUT = int(os.getenv('DB_LOGIN_TIMEOUT', '10'))
    DB_TIMEOUT = int(os.getenv('DB_TIMEOUT', '10'))
    DB_TDS_VERSION = os.getenv('DB_TDS_VERSION', '7.4')

    # Excluded document types (filter these out from analysis)
    EXCLUDED_DOCUMENT_CODES = ['XY', 'AS', 'TS']

    # Output Configuration
    OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', os.path.expanduser('~/business_reports')))

    # Report settings
    REPORT_DPI = int(os.getenv('REPORT_DPI', '300'))
    REPORT_FIGURE_SIZE = (20, 24)

    # Analysis defaults
    DEFAULT_LIMIT = int(os.getenv('DEFAULT_LIMIT', '1000'))

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def ensure_output_dir(cls):
        """Create output directory if it doesn't exist"""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return cls.OUTPUT_DIR

    @classmethod
    def has_direct_db_config(cls):
        """Check if direct database configuration is provided"""
        return all([cls.DB_HOST, cls.DB_USER, cls.DB_PASSWORD])

    @classmethod
    def validate(cls):
        """Validate configuration and check for security issues"""
        logger = logging.getLogger(__name__)

        # Check if configuration is available
        if not cls.has_direct_db_config() and not os.path.exists(cls.NCX_FILE_PATH):
            raise ValueError(
                "No valid database configuration found. "
                "Provide either NCX_FILE_PATH or DB_HOST/DB_USER/DB_PASSWORD environment variables."
            )

        # Security warnings
        if cls.has_direct_db_config():
            # Warn if using direct credentials
            logger.warning(
                "⚠️  Using direct database credentials from environment variables. "
                "Ensure these are not exposed in logs or version control."
            )

        # Check if NCX file path looks hardcoded (contains username or home directory references)
        if cls.NCX_FILE_PATH and '/home/' in cls.NCX_FILE_PATH and 'NCX_FILE_PATH' not in os.environ:
            logger.warning(
                f"⚠️  NCX_FILE_PATH appears to be hardcoded: {cls.NCX_FILE_PATH}\n"
                f"   Consider setting NCX_FILE_PATH environment variable instead."
            )

        return True


# Customer segmentation thresholds
class CustomerSegmentation:
    """Customer segmentation configuration"""
    VIP_REVENUE_THRESHOLD = 500000
    VIP_ORDERS_THRESHOLD = 5
    HIGH_VALUE_THRESHOLD = 200000
    FREQUENT_ORDERS_THRESHOLD = 10
    REGULAR_REVENUE_THRESHOLD = 50000


# Inventory velocity thresholds
class InventoryConfig:
    """Inventory analysis configuration"""
    FAST_MOVER_THRESHOLD = 5  # transactions
    SLOW_MOVER_THRESHOLD = 2  # transactions


# Profitability thresholds
class ProfitabilityConfig:
    """Profitability analysis configuration"""
    LOW_MARGIN_THRESHOLD = 10  # percent
    STAR_PRODUCT_MARGIN = 30   # percent
    CRITICAL_MARGIN = 0        # negative margin
