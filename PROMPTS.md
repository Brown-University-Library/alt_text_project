(for historical reference)

## initial prompt

```
Goal:
- To convert this pdf-checker project to an image-alt-text-maker project.

Context:

- This was a pdf-accessibility-checker project, that did the following:
	- enabled a user to upload a PDF
	- checked the pdf via veraPDF
	- sent part of the resulting veraPDF report to openrouter, with a prompt
	- displayed the LLM result to the user.

- The new functionality:
	- enable a user to upload an image
	- send the image to openrouter with a prompt
	- display the multi-modal models result to the user

- You can see the desired to architecture/functionality of: "upload --> send-to-model --> display result to user" -- is very similar.

- The new webapp should validate that the uploaded item is an image.

- It should post the image, along with a prompt (which will ask for accessibility alt-text), to openrouter.

- Maintain the existing architecture of "try processing live -- but redirect to report if timeout is exceeded".

- Maintain the existing architecture of using an array of openrouter-models.

- Maintain the existing architecture of pulling in a pattern-library header.

- Database/Model names will need to change. Do _not_ try to migrate in a way that _keeps_ any existing database data. Assume a new database, created from an updated models.py file -- will be brand-new.

- Make your best guesses as to useful-model-fields that would relate to images. But start off with a somewhat minimal set of useful-model-fields -- and offer recommendations for future ones to add.

Tasks:
- Review `alt_text_project/AGENTS.md` for coding-directives to follow.
- Create a plan to convert this pdf-webapp to the desired image-alt-text webapp.
- Incorporate into the plan your recommendation on whether to make all the changes at once -- or whether to implement parts of the  conversion in stages.
- Include any contextual information in the plan that would be useful if implementation occurs in a new work-session.
- Save the plan to `alt_text_project/PLAN__pdf_to_image_conversion_gpt5p2-m-r.md`.
- Do not change any code -- just make the plan.
```


## follow-up prompt

```
- i made a few small changes.
- i've answered questions in lines beginning with "USER-ANSWER"

Task:
- review my edits -- and make any tweaks to the plan you desire based on my edits/answers.
- again, don't change any code, just review and update the plan if you wish.
```


## follow-up prompt 2

```
- review alt_text_project/AGENTS.md for coding-directives to follow.
- review the plan at alt_text_project/PLAN__pdf_to_image_conversion_gpt5p2-m-r.md 
- implement stage-1 changes.
```
