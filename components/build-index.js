import fs from "fs";

function build(prodMode) {
    const buildFolder = prodMode ? "dist" : "build"
    fs.mkdirSync(buildFolder, { recursive: true });
    fs.copyFileSync("index.html", `${buildFolder}/index.html`)
    fs.cpSync("src/css", `${buildFolder}/css`, { recursive: true })
}

const isProd = process.argv.includes("production")
build(isProd)
