<div align="center">
  <a href="README.tr.md"><img src="https://img.shields.io/badge/Türkçe-30363D?style=for-the-badge" alt="Türkçe"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/English-30363D?style=for-the-badge" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/Deutsch-30363D?style=for-the-badge" alt="Deutsch"></a>
</div>

## Hello 👋

I’m **Kuş Bakışı**. I review games from an honest perspective, share my first impressions and real experiences, and look beyond what is popular to find great games that may have been overlooked. Alongside my YouTube videos, I share the game projects I explore and work on.

**Kuş Bakışı** means “bird’s-eye view” in Turkish and reflects my way of looking at games from a different angle. You can just call me **Birdman**.

## Spider-Man (2000) 🕸️

### What is this project?

This is my free fan project for **Spider-Man (2000)**. It is more than a simple text replacement: the Turkish version modifies and translates the game's menus, descriptions, and in-game text. The English and German versions add subtitles to video cutscenes and relevant in-game moments.

At the heart of the project is a Python based companion app that starts automatically with the game. Since the original game has no subtitle support, it recognises the current scene in the DuckStation window and places the matching subtitle on screen at the right moment. The subtitles are not baked into the videos: they appear live as you play.

<details>
  <summary><strong>How does it work?</strong></summary>
  <br>

  - Prepared visual matches recognise the current game scene.
  - The matching Turkish, English, or German subtitle is shown on screen.
  - The launcher selects the language and starts the subtitle system automatically.
  - Because it relies on image matching, the system may very rarely recognise the wrong scene.
</details>

The Windows release will use a **Setup** installer, while Ubuntu and Debian based Linux systems will use a **.deb** package. During the first setup, you will select your own game and BIOS files. The launcher will then prepare the settings and start the language you choose.

### Required files

This project does not include game or PlayStation BIOS files. All you need to play is a compatible game BIN file and a PlayStation 1 BIOS file. During the first setup, simply select them. Use **SLES-02886** for English and **SLES-02888** for German.

<img src="assets/web-divider.svg" width="100%" alt="">

## ⭐ Retroloji

<table>
  <tr>
    <td width="96" align="center">
      <a href="https://www.youtube.com/@retroloji">
        <img src="assets/retroloji.webp" width="72" alt="Retroloji">
      </a>
    </td>
    <td>
      <a href="https://www.youtube.com/@retroloji"><strong>Retroloji</strong></a><br>
      Retro deep dives into the works that shaped our past and present.
    </td>
  </tr>
</table>

<div align="center">
  Thanks to Retroloji for supporting this project.
</div>

## ☕ Buy me a coffee

If you enjoyed this project and would like to buy me a coffee, you can use the support link below. Support is completely optional; the project will always remain free.

<div align="center">
  <a href="https://github.com/sponsors/kusbakisiyt">
    <img src="assets/coffee-button.svg" width="520" alt="Buy me a coffee through GitHub Sponsors">
  </a>
</div>
