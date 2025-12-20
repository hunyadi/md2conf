# Integration Tests

This directory contains integration tests that verify md2conf works correctly with a real Confluence instance.

## Overview

The integration tests **automatically**:
1. **Create test pages** in Confluence (or reuse existing ones)
2. **Inject page IDs** into sample markdown files  
3. **Run tests** that synchronize/update those pages
4. **Optionally clean up** test pages after completion

This approach allows tests to run from scratch **without manual Confluence setup**.

## Architecture

### Test Fixtures (`fixtures.py`)

The `IntegrationTestFixture` class provides:
- **Page creation**: `get_or_create_test_page()` creates pages or finds existing ones
- **Caching**: Stores page IDs in `.test_pages.json` to avoid recreating pages
- **Cleanup**: `cleanup()` optionally deletes test pages and cache

### Test Setup (`test_api.py`)

The `setUpModule()` function:
1. Reads `CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID` environment variable
2. Creates main test pages using `IntegrationTestFixture`
3. Calls `_write_page_ids_to_samples()` to inject IDs into `sample/` files
4. Reuses `SynchronizingProcessor._update_markdown()` for consistency

### Sample Files

Sample markdown files in `../sample/` directory serve dual purposes:
- **Example documentation** for users
- **Test fixtures** with injected `<!-- confluence-page-id: ... -->` comments

## Prerequisites

### Required Software

- A Confluence Cloud, Server, or Data Center instance
- Valid Confluence credentials with appropriate permissions
- Python environment with md2conf installed
- **Parent page ID**: An existing Confluence page to nest test pages under

## Configuration

### Required Environment Variables

```bash
export CONFLUENCE_DOMAIN='your-domain.atlassian.net'
export CONFLUENCE_PATH='/wiki/'
export CONFLUENCE_USER_NAME='your-email@example.com'
export CONFLUENCE_API_KEY='your-api-key-here'
export CONFLUENCE_SPACE_KEY='TEST'  # or your test space key

# CRITICAL: Required for test setup
export CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID='123456'

# Optional: Test specific features
export TEST_MERMAID=1
export TEST_PLANTUML=1
export PLANTUML_JAR='path/to/plantuml.jar'

# Optional: Clean up test pages after completion
export CLEANUP_TEST_PAGES=false
```

### Generating an API Key

**Confluence Cloud:**

1. Go to <https://id.atlassian.com/manage-profile/security/api-tokens>
2. Click "Create API token"
3. Give it a label (e.g., "md2conf integration tests")
4. Copy the token and use it as `CONFLUENCE_API_KEY`

**Confluence Server/Data Center:**

- Use your regular password as the API key, or configure a personal access token if available

### Required Permissions

Your Confluence user must have permissions to:

- View pages in the test space
- Create pages
- Update pages
- Upload attachments
- Delete pages (if using `CLEANUP_TEST_PAGES`)

## How It Works

### 1. Initial Setup (First Run)

When you run tests for the first time:

```
setUpModule()
  ├─ Read CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID from environment
  ├─ Create "Publish Markdown to Confluence" page → ID: 917515
  ├─ Create "Test Page for Attachments" page → ID: 917534
  └─ _write_page_ids_to_samples()
       ├─ Create/find pages for each sample file
       └─ Inject page IDs into markdown files:
            sample/index.md          → <!-- confluence-page-id: 917515 -->
            sample/attachments.md    → <!-- confluence-page-id: 917534 -->
            sample/code.md           → <!-- confluence-page-id: 917520 -->
            sample/panel.md          → <!-- confluence-page-id: 917521 -->
            sample/plantuml.md       → <!-- confluence-page-id: 917522 -->
            sample/parent/index.md   → <!-- confluence-page-id: 917523 -->
            sample/parent/child.md   → <!-- confluence-page-id: 917524 -->
```

### 2. Test Execution

```
test_synchronize()
  └─ Publisher reads sample/index.md
       ├─ Finds <!-- confluence-page-id: 917515 --> in file
       ├─ Fetches existing page 917515 from Confluence
       └─ Updates page content with converted markdown
```

### 3. Subsequent Runs

A `.test_pages.json` cache file stores created page IDs:

```json
{
  "TEST:Publish Markdown to Confluence": "917515",
  "TEST:Test Page for Attachments": "917534",
  "TEST:Fenced code blocks": "917520"
}
```

On subsequent runs, pages are **reused** (not recreated), making tests faster.

### 4. Cleanup (Optional)

```
tearDownModule()  # if CLEANUP_TEST_PAGES=true
  └─ Delete all cached test pages
  └─ Remove .test_pages.json
```

## Running Tests

### Run All Integration Tests

```bash
python -m unittest discover -s integration_tests
```

### Run Specific Test File

```bash
python -m unittest integration_tests.test_api
python -m unittest integration_tests.test_csf
```

### Run with Verbose Output

```bash
python -m unittest discover -s integration_tests -v
```

### Clean Up Test Pages After Run

By default, test pages are left in Confluence for inspection. To automatically delete them:

```bash
CLEANUP_TEST_PAGES=1 python -m unittest discover -s integration_tests
```

## Automated Test Setup

The integration tests use `fixtures.py` to automatically create required test pages. **You do not need to manually create pages** in Confluence before running tests.

### How It Works

1. **First run**: Tests automatically create required pages and cache their IDs in `.test_pages.json`
2. **Subsequent runs**: Tests reuse existing pages from the cache
3. **Cache invalidation**: If cached pages are deleted in Confluence, tests detect this and recreate them automatically

### Test Page Cache

The `.test_pages.json` file stores page IDs for reuse:

```json
{
  "TEST:Feature Test Page": "1933314",
  "TEST:Image Test Page": "26837000"
}
```

**Note**: This file is automatically generated and is in `.gitignore` as it's environment-specific.

## Troubleshooting

### Tests Skip with "Test page not created"

**Cause**: `CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID` not set

**Solution**:

```bash
export CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID='your-parent-page-id'
```

### 404 Errors: "Page not found"

**Cause**: Cached page IDs reference deleted pages

**Solution**: Delete cache and re-run:

```bash
rm integration_tests/.test_pages.json
python -m unittest discover -s integration_tests -v
```

### Permission Errors

**Cause**: API user lacks permissions to create pages

**Solution**: Grant page creation rights in the test space

### Sample Files Have Unexpected Changes

**Expected Behavior**: Sample files get `<!-- confluence-page-id: ... -->` comments injected

**Note**: This is **intentional** - it makes tests realistic and self-contained. These IDs are specific to your test environment and should not be committed.

## Design Decisions

### Why Inject Page IDs into Sample Files?

1. **Realistic examples**: Sample files show actual usage with page IDs
2. **Self-contained tests**: No need for complex test data management
3. **Code reusability**: Same logic as production (`_update_markdown()`)
4. **Idempotent**: Safe to run multiple times

### Why Use a Cache File?

1. **Faster tests**: Avoid recreating pages on every run
2. **Confluence limits**: Reduce API calls
3. **Cost savings**: Minimize billable API requests (Cloud)
4. **Debugging**: Easy to see which pages were created

### Why Separate Setup from Tests?

1. **Module-level setup**: Pages created once for all tests
2. **Shared resources**: Multiple tests use same pages
3. **Cleanup control**: Optional deletion via environment variable

## Contributing

When adding new integration tests:

1. **Add sample file** to `../sample/` if needed
2. **Update `sample_files` dict** in `_write_page_ids_to_samples()`
3. **Use existing test pages** where possible (reuse `FEATURE_TEST_PAGE_ID`)
4. **Document new tests** in this README

## References

- [CONTRIBUTING.md](../CONTRIBUTING.md) - General contribution guidelines
- [fixtures.py](fixtures.py) - Test fixture implementation
- [test_api.py](test_api.py) - API integration tests
- [test_csf.py](test_csf.py) - CSF generation tests
- [GitHub Actions Workflow](../.github/workflows/integration-tests.yml) - CI/CD setup


```bash
rm integration_tests/.test_pages.json
```

## Test Files

- `test_api.py` - Tests Confluence API interactions (page creation, updates, attachments)
- `test_csf.py` - Tests Confluence Storage Format XHTML generation
- `fixtures.py` - Automated test page setup and management
- `generate_test_summary.py` - Generate test summary with page URLs (used by CI/CD)
- `.test_pages.json` - Cached page IDs (auto-generated, gitignored)

## Troubleshooting

### "Missing required environment variables"

Ensure all five environment variables are set:

- `CONFLUENCE_DOMAIN`
- `CONFLUENCE_PATH`
- `CONFLUENCE_USER_NAME`
- `CONFLUENCE_API_KEY`
- `CONFLUENCE_SPACE_KEY`

Verify with:

```bash
env | grep CONFLUENCE
```

### Clearing the test page cache

To force recreation of test pages:

```bash
rm integration_tests/.test_pages.json
```

## Advanced Usage

### Using a Different Test Space

Create a dedicated test space for integration tests to avoid cluttering production spaces:

```bash
export CONFLUENCE_SPACE_KEY='INTTEST'
```

## GitHub Actions Integration

A GitHub Actions workflow is available at [`.github/workflows/integration-tests.yml`](../.github/workflows/integration-tests.yml) to run integration tests automatically.

### Setup

Configure the following in your GitHub repository (Settings → Secrets and variables → Actions):

**Secret** (sensitive credential):

- `CONFLUENCE_API_KEY` - Your Confluence API token

**Variables** (non-sensitive configuration):

- `CONFLUENCE_DOMAIN` - Your Confluence domain (e.g., `example.atlassian.net`)
- `CONFLUENCE_USER_NAME` - Your Confluence user email
- `CONFLUENCE_SPACE_KEY` - Test space key (e.g., `TEST`)
- `CONFLUENCE_PATH` - Optional, defaults to `/wiki/`

Using variables instead of secrets for non-sensitive information makes it easier to view and update configuration values.

### Workflow Features

The workflow automatically:

1. Sets up Python, Java (for PlantUML), and Node.js (for Mermaid)
2. Runs all integration tests
3. Generates a summary with clickable links to test pages in Confluence
4. Uploads test artifacts if tests fail

### Test Summary

After the workflow runs, view the job summary to see:

- List of all test pages created with direct links to Confluence
- Quick links to the test space
- Test page IDs for reference

### Running Manually

You can trigger the workflow manually from the Actions tab:

1. Go to Actions → Integration Tests
2. Click "Run workflow"
3. Select your branch
4. Optionally enable "Delete test pages after run" to clean up

### When It Runs

The workflow runs only on manual trigger via the Actions tab. This prevents unnecessary test runs against the live Confluence instance on every commit or pull request.
