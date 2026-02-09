# About the experimental Image Alt-Text Maker

- [Purpose](#purpose)
- [Limitations](#limitations)
- [image alt text](#image-alt-text)
- [this webapp's output](#this-webapps-output)
- [Usage](#usage)

---


## Purpose 

This is an _experimental_ webapp. It serves the following purposes:

- To see if we could use a large-language model (LLM) to give staff and users friendly, useful alt-text suggestions for images.

- To experiment with an "upload and hand-off-to-a-model" architecture because it could be extremely useful for improving the accessibility of a variety of other media.

- To show [OIT][oit] and [CCV][ccv] a working implementation of this architecture -- so we can explore ways we might work with them to use their models for improved privacy, quality, and scalability. 

---


## Limitations

### Privacy

**Don't submit anything you want to keep private.**

We send image data to third-party models via OpenRouter. If privacy is a concern, avoid uploading sensitive images.

Official Brown models offer privacy guarantees that this webapp doesn't.

### Capability

Currently, we're using a free [OpenRouter][or] account, using one of a few free models, which are less capable than models we hope to use in the future.

### Scalability

Our free account is limited to 50 requests per day. 

Due to this, we're initially only opening this up to library-staff. 

If this proves useful, and we're able to access a Brown model, we'll open this up to the Brown community, and eventually may implement API features on the drawing-board.

_If we're able to work with OIT and CCV to point to official Brown models, we'll note that here. That would address the privacy, capability, and scalability limitations._


---

## Image alt text

Alt text is a concise written description of an image for people who use screen readers or cannot see the image. Good alt text focuses on the most important visual details and avoids extra or redundant phrasing.


---

## this webapp's output

zThis webapp sends the uploaded image to a multimodal OpenRouter model with a prompt that asks for concise, accessibility-focused alt text.

Here's the [current prompt][prompt]. It will likely change over time as we experiment.

---


## Usage

Typically, you'll select and submit your image file. Usually within 20-seconds, you'll be redirected to the report page. Most of the time, the report page will show suggested alt text at the top.

Copy the url if you want to review or share the report.

If something goes wrong, you'll still be directed to the report page, but it will show a problem with the alt-text suggestion. Still, save that url and try to access it again later. We plan to implement a script to check for temporarily failed jobs and retry them.

Let us know via the feedback link on each page if you have any problems or questions.

---

[ccv]: <https://ccv.brown.edu/>
[oit]: <https://it.brown.edu/>
[or]: <https://openrouter.ai/>
[prompt]: <https://github.com/Brown-University-Library/alt_text_project/blob/main/alt_text_app/lib/prompt.md>
