# Security Guidelines

## Credential Management

### ⚠️ CRITICAL: Never Commit Credentials

**Files to NEVER commit:**
- `.env` - Contains environment variables with credentials
- `connections.ncx` - Contains encrypted database passwords
- Any file with actual database credentials

### Recommended Practices

#### 1. For Local Development

Use a `.env` file (already in `.gitignore`):

```bash
# Copy the example file
cp .env.example .env

# Edit with your credentials
nano .env
```

**Install python-dotenv for automatic .env loading:**
```bash
pip install python-dotenv
```

#### 2. For Production Environments

**Use environment variables:**
```bash
export DB_HOST=your-server
export DB_USER=your-user
export DB_PASSWORD=your-password
python business_analyzer_combined.py
```

**Or use a secret management service:**
- AWS Secrets Manager
- Azure Key Vault
- HashiCorp Vault
- Google Cloud Secret Manager

#### 3. For CI/CD Pipelines

Use encrypted secrets provided by your CI/CD platform:
- GitHub Actions: Repository Secrets
- GitLab CI: CI/CD Variables (masked)
- Jenkins: Credentials Plugin
- Azure DevOps: Variable Groups (secret)

### Navicat NCX Files

If using Navicat `.ncx` files:

1. **Store outside the repository:**
   ```bash
   export NCX_FILE_PATH=~/secure-location/connections.ncx
   ```

2. **Or encrypt with additional layer:**
   - Use file system encryption (LUKS, BitLocker)
   - Store in encrypted cloud storage

3. **Limit file permissions:**
   ```bash
   chmod 600 ~/path/to/connections.ncx
   ```

### Checking for Exposed Credentials

**Before committing, always check:**
```bash
# Check what you're about to commit
git diff --cached

# Search for potential secrets
git grep -i password
git grep -i secret
git grep -i credential
```

**If you accidentally committed credentials:**

1. **Change the passwords immediately**
2. **Remove from git history:**
   ```bash
   # Use BFG Repo-Cleaner or git-filter-branch
   # See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
   ```

3. **Force push (coordinate with team):**
   ```bash
   git push --force
   ```

### Database Connection Security

1. **Use SSL/TLS connections when possible**
2. **Implement connection encryption**
3. **Use least-privilege database accounts**
4. **Rotate credentials regularly**
5. **Monitor database access logs**

### Environment-Specific Recommendations

**Development:**
- Use `.env` file (not committed)
- Use separate dev database with test data

**Staging:**
- Use environment variables
- Separate credentials from production

**Production:**
- Use secret management service
- Enable audit logging
- Implement credential rotation
- Use read-only accounts for analysis

### Compliance Considerations

If handling sensitive data:
- **GDPR**: Ensure data minimization and encryption
- **HIPAA**: Use compliant credential storage
- **PCI-DSS**: Follow key management requirements
- **SOC 2**: Implement access controls and audit trails

## Reporting Security Issues

If you discover a security vulnerability:
1. **Do NOT open a public issue**
2. Email the maintainer directly (see README)
3. Include detailed description and steps to reproduce
4. Allow time for patch before public disclosure
