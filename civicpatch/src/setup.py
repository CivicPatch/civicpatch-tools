def post_install():
    """
    Runs Playwright browser installation after Poetry install.
    """
    try:
        import spacy
        # spacy.cli.download("en_core_web_trf")
        # spacy.cli.download("en_core_web_sm")
        spacy.cli.download("en_core_web_md")
        # spacy.cli.download("en_core_web_lg")
        print("Playwright and spaCy models installed successfully.")

    except Exception as e:
        print(f"Error during Playwright installation: {e}")

if __name__ == "__main__":
    post_install()