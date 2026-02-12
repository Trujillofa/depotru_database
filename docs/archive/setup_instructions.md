# Setup Instructions

## Quick Start

1. **Copy the example configuration file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   nano .env
   ```

3. **Choose one of two authentication methods:**

   **Option A: Use Navicat NCX File**
   ```
   NCX_FILE_PATH=/path/to/your/connections.ncx
   ```

   **Option B: Direct Database Credentials**
   ```
   DB_HOST=your-server-host
   DB_PORT=1433
   DB_USER=your-username
   DB_PASSWORD=your-password
   DB_NAME=SmartBusiness
   ```

4. **Run the analyzer:**
   ```bash
   python business_analyzer_combined.py --limit 5000
   ```

## Configuration Options

All configuration can be set via environment variables or in the `config.py` file.

See `.env.example` for all available options.

## Output

Reports will be saved to: `~/business_reports/` (configurable via `OUTPUT_DIR`)
