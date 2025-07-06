from pydantic import BaseModel, Field
from typing import List

class CandidateAnalysis(BaseModel):
    candidate_name: str = Field(description="The candidate's name, extracted from the resume.")
    score: int = Field(description="A score from 0 to 100 representing the fit for the job.", ge=0, le=100)
    summary: str = Field(description="A 2-3 sentence summary of the candidate's fit.")
    reasoning: str = Field(description="Detailed bullet-point reasoning for the score, highlighting strengths and weaknesses.")
    is_recommended: bool = Field(description="A simple boolean indicating if the candidate is recommended for an interview.")