# GitHub Setup Guide

## Step 1: Create a GitHub Repository

1. Go to https://github.com and sign in
2. Click the "+" icon in the top right → "New repository"
3. Repository name: `DefiTracker`
4. Description: "Multi-chain DeFi APR tracker for tracking APRs across multiple blockchain networks"
5. Choose Public or Private
6. **DO NOT** initialize with README, .gitignore, or license (we already have these)
7. Click "Create repository"

## Step 2: Initialize Git (if not already done)

Open a terminal in your project directory:

```bash
# Check if git is already initialized
git status

# If not initialized, run:
git init
```

## Step 3: Add All Files

```bash
# Add all files (except those in .gitignore)
git add .

# Check what will be committed
git status
```

**Important:** Make sure `config/database.yaml` is NOT in the list (it should be ignored because it contains your password).

## Step 4: Create Initial Commit

```bash
git commit -m "Initial commit: Multi-chain DeFi APR tracker framework"
```

## Step 5: Connect to GitHub Repository

```bash
# Add your GitHub repository as remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/DefiTracker.git

# Verify the remote was added
git remote -v
```

## Step 6: Push to GitHub

```bash
# Push to GitHub (first time)
git branch -M main
git push -u origin main
```

You'll be prompted for your GitHub username and password (or personal access token).

## Step 7: Verify on GitHub

1. Go to your repository on GitHub
2. Verify all files are there
3. **Important:** Verify that `config/database.yaml` is NOT visible (it should be ignored)

## Setting Up on Another Computer

### Step 1: Clone the Repository

```bash
# Navigate to where you want the project
cd ~/Projects

# Clone the repository
git clone https://github.com/YOUR_USERNAME/DefiTracker.git

# Navigate into the project
cd DefiTracker
```

### Step 2: Create Database Configuration

```bash
# Copy the template
cp config/database.yaml.template config/database.yaml

# Edit config/database.yaml with your database credentials
nano config/database.yaml
# Or use your preferred editor: vim, code, etc.
```

Fill in your PostgreSQL password and other database settings.

### Step 3: Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Set Up Database

Follow the instructions in `DATABASE_SETUP_GUIDE.md`:

```bash
# Run database setup
python src/database/setup.py
```

## Updating the Repository

### When You Make Changes

```bash
# Check what changed
git status

# Add changed files
git add .

# Commit changes
git commit -m "Description of your changes"

# Push to GitHub
git push
```

### When You Pull Latest Changes (on another computer)

```bash
# Pull latest changes
git pull
```

## Important Notes

### Files NOT Committed (Protected by .gitignore)

- ✅ `config/database.yaml` - Contains your password (not committed)
- ✅ `venv/` - Virtual environment (not needed in repo)
- ✅ `__pycache__/` - Python cache files
- ✅ `.env` - Environment variables (if you add them later)

### Files That ARE Committed

- ✅ `config/database.yaml.template` - Template for others to copy
- ✅ `config/chains.yaml` - Chain configuration (no passwords)
- ✅ All source code
- ✅ Documentation files
- ✅ Migration files

## Troubleshooting

### Error: "remote origin already exists"
```bash
# Remove existing remote
git remote remove origin

# Add again with correct URL
git remote add origin https://github.com/YOUR_USERNAME/DefiTracker.git
```

### Error: "authentication failed"
- Use a Personal Access Token instead of password:
  1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
  2. Generate new token with `repo` scope
  3. Use the token as your password when pushing

### Error: "database.yaml not found" on new computer
- You need to copy the template: `cp config/database.yaml.template config/database.yaml`
- Then edit it with your database credentials

## Security Best Practices

1. ✅ **Never commit passwords** - `database.yaml` is in .gitignore
2. ✅ **Use templates** - `database.yaml.template` shows what's needed
3. ✅ **Review before pushing** - Always check `git status` before committing
4. ✅ **Use environment variables** - For production, consider using `.env` files (also in .gitignore)

