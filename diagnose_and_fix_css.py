#!/usr/bin/env python3
"""
Diagnose and fix styles-m.css compilation issue
"""
import paramiko
import time

# Server credentials
hostname = "174.142.205.80"
username = "deptrujillob2c"
password = "RX}MUWwSnK5G"
magento_root = "/home/deptrujillob2c/public_html"

def run_command(ssh, command, description):
    """Execute command via SSH and return output"""
    print(f"\n{'='*60}")
    print(f"EXECUTING: {description}")
    print(f"COMMAND: {command}")
    print('='*60)

    stdin, stdout, stderr = ssh.exec_command(command)
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')

    if output:
        print("OUTPUT:")
        print(output)
    if error:
        print("ERROR:")
        print(error)

    return output, error

try:
    # Connect to server
    print("Connecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password)
    print("✓ Connected successfully")

    # Step 1: Check styles-m.less content
    print("\n" + "="*60)
    print("STEP 1: Examining styles-m.less")
    print("="*60)
    cmd = f"cat {magento_root}/app/design/frontend/Olegnax/athlete2/web/css/styles-m.less"
    run_command(ssh, cmd, "Read styles-m.less")

    # Step 2: Check _reset.less content
    print("\n" + "="*60)
    print("STEP 2: Examining source/_reset.less")
    print("="*60)
    cmd = f"head -30 {magento_root}/app/design/frontend/Olegnax/athlete2/web/css/source/_reset.less"
    run_command(ssh, cmd, "Read first 30 lines of _reset.less")

    # Step 3: Create PHP script to test LESS compilation
    print("\n" + "="*60)
    print("STEP 3: Testing manual LESS compilation")
    print("="*60)

    php_test_script = """<?php
require '/home/deptrujillob2c/public_html/vendor/autoload.php';

echo "\\n=== Testing LESS Compilation ===\\n\\n";

// Test 1: Compile styles-m.less
echo "Test 1: Compiling styles-m.less...\\n";
try {
    $options = [
        'compress' => false,
        'sourceMap' => false,
    ];

    $parser = new \\Less_Parser($options);

    // Set variables that might be needed
    $parser->ModifyVars([
        'media-common' => 'true',
        'media-target' => 'mobile'
    ]);

    $parser->parseFile('/home/deptrujillob2c/public_html/app/design/frontend/Olegnax/athlete2/web/css/styles-m.less');
    $css = $parser->getCss();

    echo "SUCCESS! Compiled " . strlen($css) . " bytes\\n";

    if (strlen($css) > 0) {
        echo "First 500 characters:\\n";
        echo substr($css, 0, 500) . "...\\n";
    } else {
        echo "WARNING: CSS output is empty!\\n";
    }
} catch (Exception $e) {
    echo "ERROR: " . $e->getMessage() . "\\n";
    echo "Exception class: " . get_class($e) . "\\n";
    if (method_exists($e, 'getTraceAsString')) {
        echo "Stack trace:\\n" . $e->getTraceAsString() . "\\n";
    }
}

echo "\\n";

// Test 2: Compile styles-l.less for comparison
echo "Test 2: Compiling styles-l.less (for comparison)...\\n";
try {
    $parser2 = new \\Less_Parser();
    $parser2->parseFile('/home/deptrujillob2c/public_html/app/design/frontend/Olegnax/athlete2/web/css/styles-l.less');
    $css2 = $parser2->getCss();

    echo "SUCCESS! Compiled " . strlen($css2) . " bytes\\n";
} catch (Exception $e) {
    echo "ERROR: " . $e->getMessage() . "\\n";
}

echo "\\n=== Test Complete ===\\n";
"""

    # Write test script to server
    cmd = f'cat > {magento_root}/test_less_compilation.php << \'PHPEOF\'\n{php_test_script}\nPHPEOF'
    run_command(ssh, cmd, "Create PHP test script")

    # Run the test script
    cmd = f"cd {magento_root} && /usr/local/bin/php test_less_compilation.php 2>&1"
    output, error = run_command(ssh, cmd, "Execute LESS compilation test")

    # Step 4: Check current deployment mode
    print("\n" + "="*60)
    print("STEP 4: Checking Magento mode")
    print("="*60)
    cmd = f"cd {magento_root} && /usr/local/bin/php bin/magento deploy:mode:show 2>&1"
    run_command(ssh, cmd, "Check deployment mode")

    # Step 5: Check if CSS files exist
    print("\n" + "="*60)
    print("STEP 5: Checking for existing CSS files")
    print("="*60)
    cmd = f"find {magento_root}/pub/static/frontend/Olegnax/athlete2 -name 'styles-*.css' 2>/dev/null | head -20"
    run_command(ssh, cmd, "Find styles CSS files")

    # Clean up test script
    cmd = f"rm {magento_root}/test_less_compilation.php"
    ssh.exec_command(cmd)

    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)

    ssh.close()

except Exception as e:
    print(f"\nConnection Error: {e}")
    print(f"Type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
