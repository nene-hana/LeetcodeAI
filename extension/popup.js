let generatedBlogMarkdown = "";
let generatedProblemTitle = "";
let generatedBlog = "";

function convertMarkdownToHTML(markdown) {
    return markdown
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')
        .replace(/\*(.*)\*/gim, '<i>$1</i>')
        .replace(/\n/gim, '<br>');
}

document.addEventListener('DOMContentLoaded', async () => {

    const statusEl = document.getElementById('status');
    const platformInputs =
        Array.from(
            document.querySelectorAll(
                'input[name="platform"]'
            )
        );

    const draftInput =
        document.getElementById('draftMode');

    chrome.storage.local.get({
        publishingPlatforms: ['devto'],
        publishAsDraft: false
    }, ({ publishingPlatforms, publishAsDraft }) => {

        platformInputs.forEach(input => {
            input.checked =
                publishingPlatforms.includes(
                    input.value
                );
        });

        draftInput.checked =
            publishAsDraft;
    });

    const savePublishingSettings = () => {

        const selectedPlatforms =
            platformInputs
                .filter(input => input.checked)
                .map(input => input.value);

        if (selectedPlatforms.length === 0) {

            const devtoInput =
                platformInputs.find(
                    input => input.value === 'devto'
                );

            if (devtoInput) {
                devtoInput.checked = true;
                selectedPlatforms.push('devto');
            }
        }

        chrome.storage.local.set({
            publishingPlatforms:
                selectedPlatforms,
            publishAsDraft:
                draftInput.checked
        });
    };

    platformInputs.forEach(input =>
        input.addEventListener(
            'change',
            savePublishingSettings
        )
    );

    draftInput.addEventListener(
        'change',
        savePublishingSettings
    );

    // Load generated blog from storage
    chrome.storage.local.get(
        [
            "generatedBlog",
            "generatedProblemTitle"
        ],
        (res) => {

            if (res.generatedBlog) {

                generatedBlog =
                    res.generatedBlog;

                generatedBlogMarkdown =
                    res.generatedBlog;

                generatedProblemTitle =
                    res.generatedProblemTitle
                    || "leetcode-blog";

                document
                    .getElementById("exportSection")
                    .style.display = "block";

                document
                    .getElementById("previewSection")
                    .style.display = "block";

                document
                    .getElementById("blogEditor")
                    .value = generatedBlog;
            }
    });

    statusEl.innerText =
        "Publishing automation active";
});

// Generate button
document.getElementById('generateBtn')
.addEventListener('click', async () => {

    const statusEl =
        document.getElementById('status');

    const btn =
        document.getElementById('generateBtn');

    btn.disabled = true;

    statusEl.innerText =
        "Generating blog...";

    statusEl.className = "";

    try {

        const tabs =
            await chrome.tabs.query({
                active: true,
                currentWindow: true
            });

        const tab = tabs[0];

        const customPrompt =
            document
                .getElementById('customPrompt')
                .value
                .trim();

        if (
            !tab ||
            !tab.url ||
            !tab.url.includes(
                "leetcode.com/problems/"
            )
        ) {

            statusEl.innerText =
                "Please open a LeetCode problem page!";

            statusEl.className =
                "error-status";

            btn.disabled = false;

            return;
        }

        try {

            await chrome.tabs.sendMessage(
                tab.id,
                {
                    type: 'MANUAL_TRIGGER',
                    custom_prompt: customPrompt
                }
            );

        } catch (msgErr) {

            console.log(
                "Re-injecting content script..."
            );

            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['content.js']
            });

            setTimeout(async () => {

                try {

                    await chrome.tabs.sendMessage(
                        tab.id,
                        {
                            type: 'MANUAL_TRIGGER'
                        }
                    );

                } catch (e2) {

                    statusEl.innerText =
                        "Error: Please refresh LeetCode page!";

                    statusEl.className =
                        "error-status";

                    btn.disabled = false;
                }

            }, 500);
        }

    } catch (e) {

        console.error("Popup Error:", e);

        statusEl.innerText =
            "Error: " + e.message;

        statusEl.className =
            "error-status";

        btn.disabled = false;
    }
});

// Listen for blog ready event
chrome.runtime.onMessage.addListener((request) => {

    if (request.type === "BLOG_READY") {

        chrome.storage.local.get(
            [
                "generatedBlog",
                "generatedProblemTitle"
            ],
            (res) => {

                if (res.generatedBlog) {

                    generatedBlog =
                        res.generatedBlog;

                    generatedBlogMarkdown =
                        res.generatedBlog;

                    generatedProblemTitle =
                        res.generatedProblemTitle
                        || "leetcode-blog";

                    document
                        .getElementById("exportSection")
                        .style.display = "block";

                    document
                        .getElementById("previewSection")
                        .style.display = "block";

                    document
                        .getElementById("blogEditor")
                        .value = generatedBlog;

                    document
                        .getElementById("status")
                        .innerText =
                        "Blog generated successfully!";

                    document
                        .getElementById("generateBtn")
                        .disabled = false;
                }
        });
    }
});

// Status updates
chrome.runtime.onMessage.addListener(
    (request) => {

    const statusEl =
        document.getElementById('status');

    const btn =
        document.getElementById('generateBtn');

    if (request.type === 'STATUS_UPDATE') {

        statusEl.innerText =
            request.message;

        statusEl.className = "";

        if (request.status === 'success') {

            statusEl.innerText =
                request.message ||
                "Successfully posted";

            statusEl.className =
                "success-status";

            btn.disabled = false;

        } else if (
            request.status === 'error'
        ) {

            statusEl.className =
                "error-status";

            btn.disabled = false;

        } else if (
            request.status === 'warning'
        ) {

            statusEl.className =
                "warning-status";

            btn.disabled = false;
        }
    }
});

// Dashboard button
document.getElementById('dashboardBtn')
.addEventListener('click', () => {

    chrome.tabs.create({
        url: chrome.runtime.getURL(
            'dashboard.html'
        )
    });
});

// Export Markdown
document
.getElementById("exportMarkdownBtn")
?.addEventListener("click", () => {

    const blob = new Blob(
        [generatedBlogMarkdown],
        { type: "text/markdown" }
    );

    const url =
        URL.createObjectURL(blob);

    const a =
        document.createElement("a");

    a.href = url;

    a.download =
        `${generatedProblemTitle}.md`;

    a.click();

    URL.revokeObjectURL(url);
});

// Export HTML
document
.getElementById("exportHTMLBtn")
?.addEventListener("click", () => {

    const html =
        convertMarkdownToHTML(
            generatedBlogMarkdown
        );

    const blob = new Blob(
        [html],
        { type: "text/html" }
    );

    const url =
        URL.createObjectURL(blob);

    const a =
        document.createElement("a");

    a.href = url;

    a.download =
        `${generatedProblemTitle}.html`;

    a.click();

    URL.revokeObjectURL(url);
});

// Export PDF
document
.getElementById("exportPDFBtn")
?.addEventListener("click", () => {

    const container =
        document.createElement("div");

    container.style.padding =
        "20px";

    container.innerHTML =
        convertMarkdownToHTML(
            generatedBlogMarkdown
        );

    html2pdf()
        .set({
            margin: 0.5,
            filename:
                `${generatedProblemTitle}.pdf`,
            image: {
                type: "jpeg",
                quality: 1
            },
            html2canvas: {
                scale: 2
            },
            jsPDF: {
                unit: "in",
                format: "a4",
                orientation: "portrait"
            }
        })
        .from(container)
        .save();
});

// Publish button
document
.getElementById("publishBtn")
?.addEventListener("click", async () => {

    const editedBlog =
        document
            .getElementById("blogEditor")
            .value;

    chrome.runtime.sendMessage({
        type: "PUBLISH_EDITED_BLOG",
        blog: editedBlog
    });

    document
        .getElementById("status")
        .innerText =
        "Publishing edited blog...";
});

// Cancel button
document
.getElementById("cancelPreviewBtn")
?.addEventListener("click", () => {

    document
        .getElementById("previewSection")
        .style.display = "none";
});