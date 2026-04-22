import requests
from langchain.tools import tool

@tool
def add(a: float, b: float) -> float:
    """
    Adds two numbers and returns the result.
    Args:
        a (float): The first number to add.
        b (float): The second number to add.
    Returns:
        float: The sum of a and b.
    """
    return a + b

@tool
def fetch_number_fact(number: int) -> str:
    """
    Fetches a fact about a number from the Numbers API.
    Args:
        number (int): The number for which to fetch a fact.
    Returns:
        str: The fact about the number or an error message.
    """
    url = f"http://numbersapi.com/{number}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        return "Could not fetch a fact about the number."