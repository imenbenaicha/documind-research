from src.documind.metadata_extraction import extract_metadata


def test_extracts_basic_scholarly_metadata():
    text = '''[Page 1]
    BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding
    Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova
    Google AI Language
    Abstract
    We introduce a new language representation model called BERT. This model is designed to pre-train deep bidirectional representations from unlabeled text.
    1 Introduction
    Recent advances in pre-trained language representations have improved many tasks.
    DOI: 10.18653/v1/N19-1423
    Keywords: language models, transformers, NLP
    '''
    result = extract_metadata(text, {}, "paper.pdf")
    assert "BERT" in result["title"]
    assert "Jacob Devlin" in result["authors"]
    assert result["doi"] == "10.18653/v1/N19-1423"
    assert "bidirectional representations" in result["abstract"]
    assert "transformers" in result["keywords"]
