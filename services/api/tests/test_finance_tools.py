import unittest

from folio_api.demo_domain import initial_state
from folio_api.finance_tools import make_tool_executor, validate_financial_answer


class FinanceToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_comparison_is_scoped(self):
        result = await make_tool_executor(initial_state(), "personal")(
            "compare_periods", {"previous": "2026-08", "current": "2026-09"}, "op"
        )
        self.assertEqual(result["differenceMinor"], 39670)

    async def test_foreign_ids_rejected(self):
        with self.assertRaises(ValueError):
            await make_tool_executor(initial_state(), "personal")(
                "get_transaction", {"id": "foreign"}, "op"
            )

    async def test_row_limit(self):
        with self.assertRaises(ValueError):
            await make_tool_executor(initial_state(), "personal")(
                "search_transactions", {"limit": 500}, "op"
            )

    async def test_no_guaranteed_capacity(self):
        r = await make_tool_executor(initial_state(), "personal")("calculate_capacity", {}, "op")
        self.assertEqual(r["status"], "needs_input")

    def test_number_grounding(self):
        tool = {"calculationId": "calculation-one", "currentMinor": 341280, "currency": "NZD"}
        self.assertTrue(validate_financial_answer("NZD 3,412.80 [calculation-one]", [tool]))
        self.assertFalse(validate_financial_answer("$3,500.00 [calculation-one]", [tool]))
        self.assertFalse(validate_financial_answer("$3,412.80", []))


class AnswerCurrencyTests(unittest.TestCase):
    def test_claim_currency_must_match_evidence(self):
        result = {"calculationId": "calc-nzd", "currentMinor": 1250, "currency": "NZD"}
        self.assertFalse(validate_financial_answer("USD 12.50 [calc-nzd]", [result]))
        self.assertFalse(validate_financial_answer("EUR 12.50 [calc-nzd]", [result]))
        self.assertTrue(validate_financial_answer("NZD 12.50 [calc-nzd]", [result]))

    def test_signed_amount_must_match_evidence(self):
        result = {"calculationId": "calc-nzd", "currentMinor": 1250, "currency": "NZD"}
        self.assertFalse(validate_financial_answer("NZD -12.50 [calc-nzd]", [result]))

    def test_citation_must_belong_to_the_claimed_value(self):
        results = [
            {"calculationId": "calc-one", "currentMinor": 1250, "currency": "NZD"},
            {"calculationId": "calc-two", "currentMinor": 9900, "currency": "USD"},
        ]
        self.assertFalse(validate_financial_answer("USD 99.00 [calc-one]", results))

    def test_extra_decimal_precision_is_not_silently_truncated(self):
        result = {"calculationId": "calc-nzd", "currentMinor": 1250, "currency": "NZD"}
        self.assertFalse(validate_financial_answer("NZD 12.501 [calc-nzd]", [result]))


class AnswerSyntaxTests(unittest.TestCase):
    def test_explicit_code_followed_by_dollar_symbol_still_enforces_currency(self):
        evidence = [{"calculationId": "calc-nzd", "currentMinor": 1250, "currency": "NZD"}]
        self.assertFalse(validate_financial_answer("USD $12.50 [calc-nzd]", evidence))
        self.assertTrue(validate_financial_answer("NZD $12.50 [calc-nzd]", evidence))

    def test_citation_substring_is_not_a_valid_citation(self):
        evidence = [{"calculationId": "calc-nzd", "currentMinor": 1250, "currency": "NZD"}]
        self.assertFalse(validate_financial_answer("NZD 12.50 [calc-nzd-forged]", evidence))


class UnsupportedMoneyGrammarTests(unittest.TestCase):
    def test_unsupported_money_grammar_is_rejected_instead_of_bypassing_validation(self):
        evidence = [{"calculationId": "calc-nzd", "currentMinor": 1250, "currency": "NZD"}]
        for claim in [
            "NZ$99.00",
            "12.50 NZD",
            "$12.50 million",
            "$12.50m",
            "€99.00",
            "£99.00",
            "99 dollars",
            "12.50 USD",
        ]:
            with self.subTest(claim=claim):
                self.assertFalse(validate_financial_answer(f"{claim} [calc-nzd]", evidence))


class CitationTokenTests(unittest.TestCase):
    def test_bounded_calculation_ids_are_not_monetary_shorthand(self):
        for suffix in ("a", "b", "k", "m"):
            calculation_id = f"category:00000000-0000-4000-8000-00000000000{suffix}:1:personal:0"
            evidence = [{"amountMinor": 58800, "currency": "NZD", "calculationId": calculation_id}]
            self.assertTrue(validate_financial_answer(f"NZD 588.00 [{calculation_id}]", evidence))
            self.assertFalse(validate_financial_answer(f"10b [{calculation_id}]", evidence))
            self.assertFalse(
                validate_financial_answer(f"NZD 588.00 [10b] [{calculation_id}]", evidence)
            )
