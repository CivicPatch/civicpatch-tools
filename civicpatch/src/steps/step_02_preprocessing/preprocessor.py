from markdownify import markdownify as md 
from .html_filter import filter_html

def run_preprocessing(input_html):
    output_html =  filter_html(input_html)

    output_md = md(output_html)
    return output_md