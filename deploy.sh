#!/usr/bin/env bash
# One-shot helper to publish this project to GitHub, ready for Streamlit Cloud.
#
# Usage:
#   ./deploy.sh <github-username> [repo-name]
#
# It will:
#   1. commit any pending changes
#   2. create the GitHub repo and push (via `gh` if installed, else via git remote)
#   3. print the exact Streamlit Community Cloud deploy URL
#
set -euo pipefail

USER="${1:-}"
REPO="${2:-demand-brief-generator}"

if [[ -z "$USER" ]]; then
  echo "Usage: ./deploy.sh <github-username> [repo-name]"
  exit 1
fi

# 1) ensure branch main + everything committed
git branch -M main 2>/dev/null || true
git add -A
git commit -m "Demand Brief Generator: publish" -q || echo "(nothing new to commit)"

# 2) create + push
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "→ Using gh to create and push $USER/$REPO ..."
  gh repo create "$USER/$REPO" --public --source=. --remote=origin --push
else
  echo "→ gh not available/authed. Create an EMPTY public repo named '$REPO' at:"
  echo "    https://github.com/new"
  echo "  then this script will push to it."
  read -r -p "Press Enter once the empty repo exists..."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$USER/$REPO.git"
  git push -u origin main
fi

echo ""
echo "✅ Pushed to https://github.com/$USER/$REPO"
echo ""
echo "▶ Deploy a public link (free) — Streamlit Community Cloud:"
echo "   https://share.streamlit.io/deploy?repository=$USER/$REPO&branch=main&mainModule=app.py"
echo "   (Optional) add OPENAI_API_KEY under the app's Secrets for the AI narrative."
