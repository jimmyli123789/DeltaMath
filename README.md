# DeltaMath Automation 

## 🔑 How to access it   
* ### 📁 Download the folder 
* ### ➕ Create an account

## ⚡ What it does 
* ### 📷 User screenshots the answer area 
* ### 🤖 Answer gets sent to the AI 
* ### 🔍 Locates the text box by image recognition (pyautogui)
* ### 📋 Copy pastes the answer onto text box via pyperclip 
* ### ➡️ Goes onto the next problem 

## 📹 Video Demo
* ### [❓Question Demo](https://youtu.be/cHFwtmW1URo)
* ### [⚙️Interface Demo](https://youtu.be/bM1w4NjWygk)

## ✨ Features 
 
* ### 🔧 Users can select their own model 
* ### ⚙️ Hotkeys to easily start and stop the automation (S) to start, (Q) to stop
* ### ⚙️ Always on top setting 
* ### ↔️ ↕️ Resizable 
* ### 📏 Adjustable token amount 
* ### ⏰ Adjustable time per question
* ### 📍 Adjustable next problem area
* ### 🔄 Toggle light and dark mode 
* ### 📜 History page to understand problems
* ### 🛡️ Login page for key security 

## ⚠️ Limitations 

* ### ✖️ Cannot do multiple choice as DeltaMath has varying amounts of choices 
* ### ✖️Cannot do questions with multiple text boxes (more than one answer)

##  📜 Research Paper 
* ### [paper](https://tyde.virginia.edu/digital-homework-the-overlooked-teen-crisis-of-academic-burnout/)
* ### Research paper mentioned that tons of homework --->  burnout
* ### Solved this problem throughout the entire program (everything was meant to make it easier to complete homwork) 

## 🤖 Working with an AI Agent - Jimmy 
* ### I specifically used the agent / AI to set up the calls and requets with openrouter. I also used the agent / AI to learn about the image recognition via pyautogui (locatecenteronscreen) which assisted me in creating a core part of the project. I  prompted the agent / AI to figure out a way to detect an image on a screen and click on that image.
* ###  The agent saved me tons of time in terms of also creating prompts to parse out the responses from the API. Deltamath requires a specific syntax, and allowing an agent to write me prompts that parses the syntax into Deltamath format was very helpful.
* ###  The agent didn't work well when I wasn't specific enough, it created a product that I didn't intend to produce.
* ###  I learned that prompting isn't just asking the AI / Agent to do something, but it is also about how to prompt it so that tokens aren't wasted.
* ### If I was doing another project regarding an agent, I would definetly start to prompt it to use less characters on my end and the outputs end. Furthermore, I've looked into a tool that compresses prompts to allow more [efficient prompting](https://github.com/microsoft/markitdown) 
## 🤖 Working with an AI Agent - Liam 
  * ###  TThe agent helped with a variety of issues, but the main ones were explaining how to design the front end and doing certain mundane coding tasks for us instead of us wasting time on basic things, like centering or color. We gave it the constraints of the project, so it mostly helped through its teaching on how to use certain aspects of the code as we coded it ourselves.
  * ### The agent was very useful for explaining new concepts, like the design of the app and how to format it. This required learning how to code on the frontend a bit, but it was a good experience, and the agent helped smooth out the errors I had as I coded.
  * ### The agent often gave us code or ideas that didn't align with our goals or the project we were making, so we often had to repeat the constraints and the idea of our project to help it get back on track. Additionally, the code it gave us sometimes conflicted with other parts of our code, so we had to spend some time helping it there.
  * ### When prompting, be as specific as possible. When asking it for help, make sure you are in the same chat as all of the previous messages, so it can reference previous topics to give it context without wasting time typing out the context yourself. Getting the prompt right for how it formats the answers in the DeltaMath answer box required a lot of trial and error, but once you find the pattern, it becomes simple to get the AI to do exactly what you want.
  * ### I think getting the AI to understand the context of its help and purpose in this project immediately would have saved us a lot of time. We wasted a lot of time prompting, realizing it was wrong, then changing the wording of the prompt over and over. If we had given it the overall context as a whole, it would have saved us a lot of time.

## 👥 Contributions 

* ### Backend - [@jimmyli123789](https://github.com/jimmyli123789)
* ### Frontend - Liam 



