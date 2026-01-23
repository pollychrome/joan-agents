# Testing Guide for Ceremony Components

## Overview

This guide documents the comprehensive testing approach for the Ceremony system components, ensuring all core functionality works correctly.

## Test Structure

### Backend Tests (`/backend/tests/`)

#### `test_ceremonies.py`
Comprehensive tests for ceremony API endpoints:

- **Template Management**
  - ✅ Create new ceremony templates
  - ✅ Retrieve all templates with filtering
  - ✅ Get specific template by ID
  - ✅ Handle non-existent templates

- **Component Management**
  - ✅ Retrieve all components
  - ✅ Get specific component by ID
  - ✅ Filter components by type
  - ✅ Validate component configurations

- **Session Management**
  - ✅ Start new ceremony sessions
  - ✅ Auto-cancel existing sessions
  - ✅ Update session progress
  - ✅ Complete sessions with output data
  - ✅ Cancel sessions
  - ✅ Retrieve session history

- **Component Configurations**
  - ✅ Writing Timer: duration presets, default values
  - ✅ Writing Area: placeholder text, WPM tracking
  - ✅ Word Counter: statistics display
  - ✅ AI Processor: available actions

### Frontend Tests (`/frontend/src/components/ceremony/components/__tests__/`)

#### `WritingTimer.test.tsx`
Tests for the Writing Timer component:
- ✅ Renders with default duration
- ✅ Displays preset duration buttons
- ✅ Changes duration on button click
- ✅ Handles custom duration input
- ✅ Enforces min/max duration limits
- ✅ Calls onComplete with correct data
- ✅ Highlights selected preset

#### `WritingArea.test.tsx`
Tests for the Writing Area component:
- ✅ Displays ready state initially
- ✅ Starts timer on button click
- ✅ Counts down correctly
- ✅ Updates word count in real-time
- ✅ Handles pause/resume functionality
- ✅ Allows session reset
- ✅ Completes when timer expires
- ✅ Calculates WPM correctly
- ✅ Focuses textarea on start

#### `WordCounter.test.tsx`
Tests for the Word Counter component:
- ✅ Displays success message
- ✅ Shows word count statistics
- ✅ Shows WPM statistics
- ✅ Shows duration statistics
- ✅ Displays content preview
- ✅ Handles long content truncation
- ✅ Respects show_stats configuration
- ✅ Calls onComplete with acknowledgment

#### `AIProcessor.test.tsx`
Tests for the AI Processor component:
- ✅ Renders AI processing interface
- ✅ Displays original content
- ✅ Shows configured action buttons
- ✅ Handles successful AI processing
- ✅ Shows error for unconfigured AI
- ✅ Handles API errors gracefully
- ✅ Disables processed actions
- ✅ Shows loading state
- ✅ Allows content copying
- ✅ Supports skip functionality
- ✅ Handles multiple AI actions

#### `TextPrompt.test.tsx`
Tests for the Text Prompt component:
- ✅ Renders text input interface
- ✅ Shows textarea for multiline mode
- ✅ Shows input for single-line mode
- ✅ Validates non-empty text
- ✅ Handles initial data
- ✅ Calls onComplete with text

## Running Tests

### Backend Tests

```bash
# Run all backend tests
cd backend
source venv/bin/activate
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_ceremonies.py

# Run specific test
pytest tests/test_ceremonies.py::test_start_ceremony_session

# Run with verbose output
pytest -v
```

### Frontend Tests

```bash
# Install test dependencies
cd frontend
npm install

# Run all tests
npm test

# Run with watch mode
npm run test:watch

# Run with coverage
npm run test:coverage

# Run specific test file
npm test WritingTimer.test.tsx
```

## Test Coverage Requirements

### Backend (70% minimum)
- API endpoints: 80%
- Models: 70%
- Core functionality: 90%

### Frontend (70% minimum)
- Components: 80%
- Utilities: 70%
- API integration: 60%

## Test Data

### Mock Data Structure
```typescript
// Writing session data
{
  word_count: 250,
  wpm: 25,
  duration_minutes: 10,
  content: "Written text..."
}

// Component config
{
  default_duration: 10,
  presets: [5, 10, 15, 30],
  placeholder: "Start writing...",
  track_wpm: true,
  show_stats: true,
  actions: ['summarize', 'bullets', 'grammar', 'topics']
}
```

## Continuous Integration

Add to CI/CD pipeline:

```yaml
# GitHub Actions example
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2

    # Backend tests
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install backend dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio

    - name: Run backend tests
      run: |
        cd backend
        pytest --cov=app --cov-fail-under=70

    # Frontend tests
    - name: Set up Node.js
      uses: actions/setup-node@v2
      with:
        node-version: '18'

    - name: Install frontend dependencies
      run: |
        cd frontend
        npm ci

    - name: Run frontend tests
      run: |
        cd frontend
        npm run test:coverage
```

## Test Patterns

### Component Testing Pattern
```typescript
describe('ComponentName', () => {
  const mockOnComplete = jest.fn();

  beforeEach(() => {
    mockOnComplete.mockClear();
  });

  test('core functionality', () => {
    // Arrange
    const config = { /* ... */ };

    // Act
    render(<Component config={config} onComplete={mockOnComplete} />);

    // Assert
    expect(screen.getByText('Expected')).toBeInTheDocument();
  });
});
```

### API Testing Pattern
```python
@pytest.mark.asyncio
async def test_api_endpoint(client, db_session):
    # Arrange
    test_data = {"key": "value"}

    # Act
    response = client.post("/api/endpoint", json=test_data)

    # Assert
    assert response.status_code == 200
    assert response.json()["key"] == "value"
```

## Troubleshooting

### Common Issues

1. **Async Tests Failing**
   - Ensure `@pytest.mark.asyncio` decorator is used
   - Check that fixtures are properly async

2. **Timer Tests Flaky**
   - Use `jest.useFakeTimers()` for consistent timing
   - Clear timers after each test

3. **API Mocks Not Working**
   - Verify mock paths match import statements
   - Clear mocks between tests

4. **Database Tests Failing**
   - Ensure test database is properly isolated
   - Check for proper transaction rollback

## Future Improvements

1. **E2E Testing**
   - Add Playwright/Cypress for full flow testing
   - Test complete ceremony execution

2. **Performance Testing**
   - Add load tests for API endpoints
   - Measure component render performance

3. **Visual Regression**
   - Add screenshot comparison tests
   - Test dark/light mode rendering

4. **Accessibility Testing**
   - Add jest-axe for a11y testing
   - Ensure keyboard navigation works

## Maintenance

- Review and update tests when adding new features
- Keep test data realistic and representative
- Document any special test setup requirements
- Monitor test execution time and optimize slow tests
- Update coverage requirements as codebase matures