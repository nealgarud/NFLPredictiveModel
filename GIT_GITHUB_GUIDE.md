# Git & GitHub Complete Guide

## Why Git Matters
- **Version Control**: Track changes, revert mistakes
- **Collaboration**: Work with others safely
- **Backup**: Your code is safe in the cloud
- **Professional**: Required for any dev job

---

## Part 1: Git Basics

### Installation
```bash
# Windows: Download from https://git-scm.com/
# Or use: winget install Git.Git

# Verify installation
git --version
```

### Initial Setup
```bash
# Set your identity (one-time)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Set default branch name
git config --global init.defaultBranch main

# Set default editor (optional)
git config --global core.editor "code --wait"  # VS Code
```

---

## Part 2: Essential Commands

### Daily Workflow

```bash
# 1. Check status (what changed?)
git status

# 2. See what changed (detailed)
git diff

# 3. Stage changes (prepare to commit)
git add file.py              # Single file
git add .                    # All files
git add *.py                 # All Python files

# 4. Commit (save snapshot)
git commit -m "Add spread prediction feature"

# 5. Push to GitHub (upload)
git push origin main
```

### Complete Workflow Example
```bash
# Start working
git status                    # See what's changed
git add SpreadPredictionCalculator.py
git commit -m "Fix divisional performance calculation"
git push origin main
```

---

## Part 3: Common Scenarios

### Scenario 1: Starting a New Project
```bash
# Initialize git in your project
cd NFLPredictiveModel
git init

# Create .gitignore (you already have this!)
# Add all files
git add .

# First commit
git commit -m "Initial commit: NFL prediction model"

# Connect to GitHub
git remote add origin https://github.com/yourusername/nfl-predictive-model.git
git branch -M main
git push -u origin main
```

### Scenario 2: Daily Development
```bash
# Morning: Get latest changes
git pull origin main

# Make changes to files...

# Afternoon: Save your work
git add .
git commit -m "Add bye week impact feature"
git push origin main
```

### Scenario 3: Undo Mistakes
```bash
# Undo changes to a file (before staging)
git checkout -- file.py

# Unstage a file (after git add)
git reset HEAD file.py

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes) - CAREFUL!
git reset --hard HEAD~1
```

### Scenario 4: See History
```bash
# View commit history
git log

# View with one line per commit
git log --oneline

# View changes in a file
git log -p SpreadPredictionCalculator.py

# See who changed what
git blame file.py
```

---

## Part 4: Branches (Advanced but Important)

### Why Branches?
- Work on features without breaking main
- Experiment safely
- Collaborate without conflicts

### Branch Workflow
```bash
# Create new branch
git checkout -b feature/bye-week-impact

# Work on feature...
git add .
git commit -m "Implement bye week feature"

# Switch back to main
git checkout main

# Merge feature into main
git merge feature/bye-week-impact

# Delete branch (after merge)
git branch -d feature/bye-week-impact
```

### Modern Branch Commands
```bash
# Create and switch (new way)
git switch -c feature/new-feature

# Switch branches
git switch main
git switch feature/new-feature
```

---

## Part 5: GitHub Workflow

### Creating a Repository

1. **On GitHub.com:**
   - Click "New repository"
   - Name: `nfl-predictive-model`
   - Choose: Public or Private
   - Don't initialize with README (you already have code)

2. **Connect your local repo:**
```bash
git remote add origin https://github.com/yourusername/nfl-predictive-model.git
git branch -M main
git push -u origin main
```

### GitHub Features

**1. README.md** (Project description)
```markdown
# NFL Predictive Model

A serverless AWS Lambda-based system for predicting NFL game outcomes.

## Features
- Spread prediction
- Team performance analysis
- Historical ATS tracking
```

**2. Issues** (Bug tracking)
- Click "Issues" → "New Issue"
- Track bugs, features, improvements

**3. Pull Requests** (Code review)
- Create branch → Make changes → Push
- Open Pull Request on GitHub
- Review changes before merging

**4. Releases** (Version tags)
```bash
# Tag a version
git tag -a v1.0.0 -m "First stable release"
git push origin v1.0.0
```

---

## Part 6: Best Practices

### Commit Messages
**Good:**
```
✅ "Add divisional performance feature"
✅ "Fix ATS calculation for home teams"
✅ "Update requirements.txt for pandas 2.0"
```

**Bad:**
```
❌ "fix"
❌ "update"
❌ "changes"
```

### Commit Frequency
- **Commit often**: After each logical change
- **Small commits**: One feature/fix per commit
- **Meaningful messages**: Describe what and why

### What NOT to Commit
- `.env` files (secrets!)
- `__pycache__/` (already in .gitignore ✅)
- `*.zip` files (deployment packages)
- IDE settings (`.vscode/`, `.idea/`)

**Your .gitignore already handles this!** ✅

---

## Part 7: Common Workflows

### Workflow 1: Feature Development
```bash
# 1. Create feature branch
git checkout -b feature/prime-time-performance

# 2. Make changes
# ... edit files ...

# 3. Commit
git add .
git commit -m "Add prime time performance feature"

# 4. Push branch
git push origin feature/prime-time-performance

# 5. On GitHub: Create Pull Request
# 6. After review: Merge PR
# 7. Delete branch
git checkout main
git pull origin main
git branch -d feature/prime-time-performance
```

### Workflow 2: Hotfix (Quick Bug Fix)
```bash
# 1. Fix on main (or create hotfix branch)
git checkout main
# ... fix bug ...

# 2. Commit and push
git add .
git commit -m "Fix: Correct spread calculation for negative spreads"
git push origin main
```

### Workflow 3: Sync with Remote
```bash
# Get latest changes
git pull origin main

# If conflicts occur:
# 1. Git will tell you which files
# 2. Open files, look for <<<<<< markers
# 3. Resolve conflicts manually
# 4. git add .
# 5. git commit -m "Resolve merge conflicts"
```

---

## Part 8: Advanced (Learn Later)

### Stashing (Save work temporarily)
```bash
# Save current work without committing
git stash

# Switch branches, do something else...

# Restore saved work
git stash pop
```

### Rebasing (Clean history)
```bash
# Instead of merge, rebase for linear history
git rebase main
```

### Cherry-picking (Copy specific commits)
```bash
# Copy a commit from another branch
git cherry-pick <commit-hash>
```

---

## Part 9: Troubleshooting

### Problem: "Your branch is ahead of origin"
**Solution:** Push your commits
```bash
git push origin main
```

### Problem: "Your branch is behind origin"
**Solution:** Pull latest changes
```bash
git pull origin main
```

### Problem: "Merge conflicts"
**Solution:** 
1. Git shows conflicted files
2. Open files, find `<<<<<<<`, `=======`, `>>>>>>>`
3. Choose which version to keep
4. Remove conflict markers
5. `git add .` then `git commit`

### Problem: "Accidentally committed secrets"
**Solution:** Remove from history (advanced)
```bash
# Use git filter-branch or BFG Repo-Cleaner
# Or: Change secrets, commit new version
```

---

## Part 10: Your Project Setup

### Current State
- ✅ You have `.gitignore` (good!)
- ❓ Are you using git? Check:
```bash
cd "C:\Users\nealg\Nfl Predictive Model\NFLPredictiveModel"
git status
```

### If Not Using Git Yet:
```bash
# Initialize
git init

# Add remote (create repo on GitHub first)
git remote add origin https://github.com/yourusername/nfl-predictive-model.git

# First commit
git add .
git commit -m "Initial commit: NFL predictive model with Phase 2 features"

# Push
git push -u origin main
```

### Recommended Branch Structure
```
main                    # Production-ready code
├── feature/bye-week    # New features
├── feature/weather     # New features
└── hotfix/spread-bug   # Quick fixes
```

---

## Quick Reference Cheat Sheet

```bash
# Setup
git init
git remote add origin <url>
git config --global user.name "Name"

# Daily
git status
git add .
git commit -m "Message"
git push origin main
git pull origin main

# Branches
git checkout -b feature/name
git switch main
git merge feature/name

# History
git log --oneline
git diff

# Undo
git checkout -- file.py
git reset HEAD file.py
```

---

## Learning Path

### Week 1: Basics
- [ ] Install Git
- [ ] Set up GitHub account
- [ ] Initialize repo
- [ ] Make first commit
- [ ] Push to GitHub

### Week 2: Daily Workflow
- [ ] Practice: add, commit, push daily
- [ ] Learn: git status, git diff
- [ ] Practice: commit messages

### Week 3: Branches
- [ ] Create feature branch
- [ ] Make changes
- [ ] Merge back to main

### Week 4: Collaboration
- [ ] Create Pull Request
- [ ] Review code
- [ ] Handle merge conflicts

---

## Resources

- **Git Docs**: https://git-scm.com/doc
- **GitHub Guides**: https://guides.github.com/
- **Interactive Tutorial**: https://learngitbranching.js.org/
- **Git Cheat Sheet**: https://education.github.com/git-cheat-sheet-education.pdf

---

## Next Steps

1. **Today**: Initialize git in your project
2. **This Week**: Make it a habit (commit daily)
3. **This Month**: Learn branches and PRs
4. **Long-term**: Use for all projects

**Pro Tip**: Commit after each feature you complete. It's like saving your game progress!

