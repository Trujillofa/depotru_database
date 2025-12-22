#!/usr/bin/env python3
"""
Test database connection for GitHub Actions
"""

import os
import sys
import pymssql

def test_connection():
    """Test database connection using environment variables"""
    try:
        # Get credentials from environment
        db_host = os.environ.get('DB_HOST', '190.60.235.209')
        db_port = int(os.environ.get('DB_PORT', '1433'))
        db_user = os.environ.get('DB_USER', 'Consulta')
        db_password = os.environ.get('DB_PASSWORD', 'Control*01')
        db_name = os.environ.get('DB_NAME', 'SmartBusiness')
        
        print(f"🔗 Testing connection to {db_host}:{db_port}...")
        print(f"📊 Database: {db_name}")
        print(f"👤 User: {db_user}")
        
        # Connect
        conn = pymssql.connect(
            server=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            login_timeout=30,
            timeout=60,
        )
        
        print("✅ Connection successful!")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM [dbo].[banco_datos]")
        count = cursor.fetchone()[0]
        cursor.close()
        
        print(f"📈 Total records in banco_datos: {count:,}")
        
        conn.close()
        print("✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
