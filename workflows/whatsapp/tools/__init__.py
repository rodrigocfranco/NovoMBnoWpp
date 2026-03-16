"""WhatsApp workflow tools — registradas no ToolNode do LangGraph."""

from workflows.whatsapp.tools.bulas_med import drug_lookup
from workflows.whatsapp.tools.calculators import medical_calculator
from workflows.whatsapp.tools.quiz_generator import quiz_generate
from workflows.whatsapp.tools.rag_medical import rag_medical_search
from workflows.whatsapp.tools.verify_paper import verify_medical_paper
from workflows.whatsapp.tools.web_search import web_search


def get_tools() -> list:
    """Return all registered LangChain tools for the WhatsApp graph."""
    return [
        rag_medical_search,
        verify_medical_paper,
        web_search,
        drug_lookup,
        medical_calculator,
        quiz_generate,
    ]
