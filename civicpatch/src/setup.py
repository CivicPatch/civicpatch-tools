def post_install():
    """
    Runs Playwright browser installation after Poetry install.
    """
    import spacy
    # spacy.cli.download("en_core_web_trf")
    # spacy.cli.download("en_core_web_sm")
    spacy.cli.download("en_core_web_md")
    # spacy.cli.download("en_core_web_lg")
    print("Playwright and spaCy models installed successfully.")

if __name__ == "__main__":
    post_install()