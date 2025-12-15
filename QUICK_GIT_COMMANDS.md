# Quick Git Commands for GitHub

## First Time Setup (On This Computer)

```bash
# 1. Initialize git (if not already done)
git init

# 2. Add all files
git add .

# 3. Check what will be committed (verify database.yaml is NOT listed)
git status

# 4. Create initial commit
git commit -m "Initial commit: Multi-chain DeFi APR tracker framework"

# 5. Add GitHub repository (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/DefiTracker.git

# 6. Push to GitHub
git branch -M main
git push -u origin main
```

## On Another Computer (Clone and Setup)

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/DefiTracker.git
cd DefiTracker

# 2. Create database config from template
cp config/database.yaml.template config/database.yaml
# Then edit config/database.yaml with your database password

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up database
python src/database/setup.py
```

## Daily Workflow

### When You Make Changes

```bash
# 1. Check what changed
git status

# 2. Add changes
git add .

# 3. Commit
git commit -m "Description of changes"

# 4. Push to GitHub
git push
```

### When You Want Latest Changes (on another computer)

```bash
git pull
```

## Verify database.yaml is Protected

Before your first commit, always check:

```bash
git status
```

You should **NOT** see `config/database.yaml` in the list. If you do, it means `.gitignore` isn't working properly.

