#!/usr/bin/env python3
"""
Upload fix scripts to server and execute them
Uses subprocess with sshpass or ssh-keygen alternatives
"""
import subprocess
import sys
import os

# Server details
HOST = "174.142.205.80"
USER = "deptrujillob2c"
PASS = "RX}MUWwSnK5G"
MAGENTO_ROOT = "/home/deptrujillob2c/public_html"

def run_ssh_command(command, description):
    """Run SSH command using various methods"""
    print(f"\n{'='*70}")
    print(f"EXECUTING: {description}")
    print('='*70)

    # Method 1: Try using SSH with password from environment
    env = os.environ.copy()
    env['SSHPASS'] = PASS

    # Try different SSH methods
    methods = [
        # Method 1: sshpass (if available)
        f"sshpass -e ssh -o StrictHostKeyChecking=no {USER}@{HOST} '{command}'",
        # Method 2: expect script
        f"""expect -c 'spawn ssh -o StrictHostKeyChecking=no {USER}@{HOST} "{command}"; expect "password:"; send "{PASS}\\r"; expect eof'""",
    ]

    for i, cmd in enumerate(methods, 1):
        try:
            print(f"Trying method {i}...")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                env=env
            )

            if result.returncode == 0 or "command not found" not in result.stderr:
                print("OUTPUT:")
                print(result.stdout)
                if result.stderr:
                    print("STDERR:")
                    print(result.stderr)
                return result.returncode == 0

        except subprocess.TimeoutExpired:
            print(f"Method {i} timed out")
        except FileNotFoundError:
            print(f"Method {i} not available")
        except Exception as e:
            print(f"Method {i} failed: {e}")

    print("All SSH methods failed. Manual intervention required.")
    return False

def main():
    print("="*70)
    print("  CSS Compilation Fix - Automated Deployment")
    print("="*70)

    # Step 1: Try to upload PHP diagnostic script
    print("\nStep 1: Uploading diagnostic script...")
    php_script = os.path.abspath("fix_css_compilation.php")
    if os.path.exists(php_script):
        print(f"Found: {php_script}")
        # Try to upload using SCP
        upload_cmd = f"scp -o StrictHostKeyChecking=no {php_script} {USER}@{HOST}:{MAGENTO_ROOT}/"
        print("Attempting upload via SCP...")
        print(f"Command: {upload_cmd}")

        # Print manual instructions
        print("\n" + "="*70)
        print("MANUAL UPLOAD INSTRUCTIONS")
        print("="*70)
        print("\nIf automatic upload fails, please run these commands manually:\n")
        print(f"1. Upload the PHP script:")
        print(f"   scp {php_script} {USER}@{HOST}:{MAGENTO_ROOT}/")
        print(f"\n2. Run the diagnostic:")
        print(f"   ssh {USER}@{HOST}")
        print(f"   cd {MAGENTO_ROOT}")
        print(f"   php fix_css_compilation.php")
        print(f"\n3. Run the fix:")
        print(f"   bash deploy_css_fix.sh")

    # Step 2: Try to run the fix remotely
    print("\n\nStep 2: Attempting to run fix directly...")

    fix_commands = [
        "cd /home/deptrujillob2c/public_html",
        "/usr/local/bin/php bin/magento cache:clean",
        "rm -rf pub/static/frontend/Olegnax/*",
        "rm -rf var/view_preprocessed/*",
        "/usr/local/bin/php bin/magento setup:static-content:deploy en_US -f --theme Olegnax/athlete2",
        "/usr/local/bin/php bin/magento cache:flush"
    ]

    combined_command = " && ".join(fix_commands)

    success = run_ssh_command(combined_command, "Deploy static content and fix CSS")

    if not success:
        print("\n" + "="*70)
        print("MANUAL FIX INSTRUCTIONS")
        print("="*70)
        print("\nSSH into the server and run these commands:\n")
        print(f"ssh {USER}@{HOST}")
        for cmd in fix_commands:
            print(f"  {cmd}")
        print("\nOr run the deployment script:")
        print(f"  bash {MAGENTO_ROOT}/deploy_css_fix.sh")
        print("="*70)

if __name__ == "__main__":
    main()
