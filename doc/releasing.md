# Releasing a new version of odin-monitor

## One-time setup (already done for this repo)

### 1. Configure Trusted Publishing on PyPI

Go to https://pypi.org/manage/project/odin-monitor/settings/publishing/ and add a trusted publisher:

| Field | Value |
|---|---|
| Owner | `arvestad` |
| Repository | `odin` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

This lets GitHub Actions publish to PyPI without storing any API tokens.

### 2. Create the `pypi` environment on GitHub

Go to https://github.com/arvestad/odin/settings/environments and create a new environment named `pypi`. No secrets or rules needed.

---

## How to release a new version

The version is derived automatically from the git tag — there is no version number in `pyproject.toml` to update.

**1. Tag the commit and push:**

```bash
git tag v0.5.0
git push
git push origin v0.5.0
```

If you set `git config --global push.followTags true`, a plain `git push` will include tags automatically and the second push command is not needed.

The `publish.yml` GitHub Actions workflow triggers on any tag starting with `v`, builds the package, and uploads it to PyPI automatically.

**2. Verify** at https://pypi.org/project/odin-monitor/ that the new version appears (usually within a minute or two).

---

## Version numbering

Follow [Semantic Versioning](https://semver.org/):

- **Patch** (`0.x.Y`): bug fixes, documentation
- **Minor** (`0.X.0`): new features, backwards-compatible
- **Major** (`X.0.0`): breaking API changes
