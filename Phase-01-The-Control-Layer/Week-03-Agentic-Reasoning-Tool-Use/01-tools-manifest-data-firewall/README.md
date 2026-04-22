# Custom LangChain Tools: Math & Numbers API

## Objective

Demonstrate how to create and expose standard Python functions as AI-accessible tools using LangChain’s `@tool` decorator. This project includes a simple math operation and a public API fetch, both with precise docstrings for LLM usability and comprehensive tests.

## Architecture

A dedicated Python module, [tools.py](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html), contains the custom tools. Each function is decorated with `@tool` and designed for seamless integration with LangChain agents.

### Infrastructure Details

- **Runtime:** Python 3.10+
- **Environment:** Virtualenv for dependency isolation
- **Dependencies:** `langchain`, `requests`
- **Testing:** `unittest` with `unittest.mock` for API mocking

## Lessons Learned

- **Argument Passing:** LangChain’s `@tool` decorator expects arguments as a single dictionary when using `.run()`.
- **Docstrings Matter:** LLMs rely on function docstrings to understand tool purpose and argument structure.
- **Mocking APIs:** Mocking HTTP requests ensures tests are fast, reliable, and do not depend on external services.

## Tech Stack

- **Language:** [Python](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html)
- **AI Framework:** [LangChain](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html)
- **HTTP Requests:** [requests](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html)
- **Testing:** [unittest](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html)
- **Development Tools:** [venv](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [pip](vscode-file://vscode-app/c:/Users/bobby/AppData/Local/Programs/Microsoft%20VS%20Code/560a9dba96/resources/app/out/vs/code/electron-browser/workbench/workbench.html)

## Usage

### Setup

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install langchain requests
```

### Example Usage

```
from tools import add, fetch_number_fact

# Add two numbers
result = add.run({"a": 2, "b": 3})  # Returns 5

# Fetch a number fact
fact = fetch_number_fact.run({"number": 42})  # Returns a trivia string
```

### Running Tests

```
python _test_.py
```

- The test script prints clear section headers and results for each test.
- All tests should pass if the tools are implemented and installed correctly.
