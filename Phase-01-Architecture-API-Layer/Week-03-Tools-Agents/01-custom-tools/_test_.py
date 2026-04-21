import unittest
from unittest.mock import patch, Mock

from tools import add, fetch_number_fact

class TestTools(unittest.TestCase):
    # Helper to print a section header
    def print_section(self, title):
        print(f"\n{'='*10} {title} {'='*10}")

    # Tests for add
    def test_add_positive_numbers(self):
        self.print_section("test_add_positive_numbers")
        result = add.run({"a": 2, "b": 3})
        print(f"add(2, 3) = {result}")
        self.assertEqual(result, 5, "Adding 2 and 3 should return 5")

    def test_add_negative_and_positive(self):
        self.print_section("test_add_negative_and_positive")
        result = add.run({"a": -2, "b": 5})
        print(f"add(-2, 5) = {result}")
        self.assertEqual(result, 3, "Adding -2 and 5 should return 3")

    def test_add_two_negatives(self):
        self.print_section("test_add_two_negatives")
        result = add.run({"a": -2, "b": -3})
        print(f"add(-2, -3) = {result}")
        self.assertEqual(result, -5, "Adding -2 and -3 should return -5")

    def test_add_floats(self):
        self.print_section("test_add_floats")
        result = add.run({"a": 2.5, "b": 3.1})
        print(f"add(2.5, 3.1) = {result}")
        self.assertAlmostEqual(result, 5.6, msg="Adding 2.5 and 3.1 should return approximately 5.6")

    def test_add_zero(self):
        self.print_section("test_add_zero")
        result1 = add.run({"a": 0, "b": 0})
        result2 = add.run({"a": 0, "b": 5})
        result3 = add.run({"a": 5, "b": 0})
        print(f"add(0, 0) = {result1}")
        print(f"add(0, 5) = {result2}")
        print(f"add(5, 0) = {result3}")
        self.assertEqual(result1, 0, "Adding 0 and 0 should return 0")
        self.assertEqual(result2, 5, "Adding 0 and 5 should return 5")
        self.assertEqual(result3, 5, "Adding 5 and 0 should return 5")

    # Tests for fetch_number_fact
    @patch("tools.requests.get")
    def test_fetch_number_fact_success(self, mock_get):
        self.print_section("test_fetch_number_fact_success")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "42 is the answer to life."
        mock_get.return_value = mock_response

        result = fetch_number_fact.run({"number": 42})
        print(f"fetch_number_fact(42) = {result}")
        self.assertEqual(result, "42 is the answer to life.", "Should return the correct fact for 42")
        mock_get.assert_called_once_with("http://numbersapi.com/42")

    @patch("tools.requests.get")
    def test_fetch_number_fact_failure(self, mock_get):
        self.print_section("test_fetch_number_fact_failure")
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetch_number_fact.run({"number": 999999})
        print(f"fetch_number_fact(999999) = {result}")
        self.assertEqual(result, "Could not fetch a fact about the number.", "Should handle API failure gracefully")
        mock_get.assert_called_once_with("http://numbersapi.com/999999")

    @patch("tools.requests.get")
    def test_fetch_number_fact_negative_number(self, mock_get):
        self.print_section("test_fetch_number_fact_negative_number")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "-1 is a negative number."
        mock_get.return_value = mock_response

        result = fetch_number_fact.run({"number": -1})
        print(f"fetch_number_fact(-1) = {result}")
        self.assertEqual(result, "-1 is a negative number.", "Should return fact for negative number")
        mock_get.assert_called_once_with("http://numbersapi.com/-1")

    @patch("tools.requests.get")
    def test_fetch_number_fact_non_integer(self, mock_get):
        self.print_section("test_fetch_number_fact_non_integer")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Not a number"
        mock_get.return_value = mock_response

        result = fetch_number_fact.run({"number": "notanumber"})
        print(f"fetch_number_fact('notanumber') = {result}")
        self.assertEqual(result, "Not a number", "Should handle non-integer input gracefully")
        mock_get.assert_called_once_with("http://numbersapi.com/notanumber")

if __name__ == "__main__":
    print("\nRunning all tests for custom LangChain tools...\n")
    unittest.main(verbosity=2)
    print("\nAll tests completed.\n")