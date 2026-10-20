# WebSearch service (Disabled for MVP)

class WebSearch:
    async def search(self, query: str) -> list:
        return []

    async def search_products(self, query: str) -> list:
        return []

    def format_results_for_llm(self, results: list) -> str:
        return ""

    def format_product_results_for_llm(self, results: list) -> str:
        return ""

websearch = WebSearch()
