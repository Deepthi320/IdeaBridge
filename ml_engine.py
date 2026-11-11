from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOMAINS_KB = {
    "Healthcare": "hospital patient disease medical doctor treatment health clinical medicine care diagnosis vitals triage",
    "Agriculture": "crop farm soil harvest farmer agriculture plant seed irrigation fertilizer yield pest cold storage",
    "Traffic & Transport": "vehicle traffic road signal transit transport driver commute map navigation route GPS",
    "Fintech": "bank money payment fraud transaction financial wallet credit investment tax standard accounting",
    "Education": "student school university learning course teacher study curriculum exam quiz skills training peer"
}

def categorize_problem(description):
    texts = list(DOMAINS_KB.values()) + [description]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(texts)
    similarity = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
    domain_names = list(DOMAINS_KB.keys())
    best_idx = similarity.argmax()
    return domain_names[best_idx]

def calculate_match_percentage(solver_skills_str, problem_desc):
    if not solver_skills_str or not solver_skills_str.strip():
        return 25
    corpus = [solver_skills_str, problem_desc]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(corpus)
    score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    percentage = int(score * 100)
    return max(min(percentage, 95), 15) if percentage > 0 else 25
