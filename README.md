# YJViewer

| ![YJViewer's front page.](https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/yjv1.jpg) | ![YJViewer searching for cards.](https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/yjv2.jpg) | ![YJViewer at a card page.](https://raw.githubusercontent.com/iconmaster5326/YGOJSON/main/yjv3.jpg) |
| - | - | - |

A web application that lets you view [YGOJSON](https://github.com/iconmaster5326/YGOJSON) data.

# Running Locally

You'll need a modern version of [Python](https://www.python.org/), at least 3.8, to run this code. To install YJViewer from [PyPI](https://pypi.org):

```bash
python3 -m pip install yjviewer
```

Or to install it if you have the repository downloaded:

```bash
python3 -m pip install -e .
```

From there, you can run this application using `flask`:

```bash
flask --app yjviewer --debug run
```

It should then load the database and give you a URL to connect to (by default, http://localhost:5000/).

If you don't have the database downloaded, it will download it for you, but it will NOT automatically update an outdated database. You will have to either delete `data` or redownload it yourself, if you want an updated dataset!

# Running in Production

Short answer: Don't.

Long answer: This is a web application meant to be accessed by one person: you. I have not created this with scalability in mind. If you try to serve this to a network, expect problems if you get a lot of people accessing it. Furthermore, we do not cache the images we get from cross-site sources, such as Yugipedia or YGOPRODECK, and those sites have strict policies about hotlinking images from them. If you expose a YJViewer server to the outer world, expect those two sites to get mad at you if you're popular enough. I don't have the money to set up a YJViewer server myself, and even if I did solve the image-hotlinking problem, I don't know if I would have the time to maintain such a website. So don't use this in production, and don't ask me to use this in production. Saying that, if you do want to help me make YJViewer production-ready, see Contributing, below.

# Contributing

PRs are always welcome! To set up YJViewer for development, follow these steps after checking out the repository:

```bash
python3 -m pip install -e .[dev,test]
pre-commit install
```

# Changelog

## 0.2.3

* Support for YGOJSON 0.5.0.

## 0.2.2

* Fixed bug with the random sealed product button.

## 0.2.1

* Removed deprecated use of `boxImage` property.

## 0.2.0

* Added support for viewing sealed products.
* Added support for viewing set pack distributions.

## 0.1.1

* Fix image loading.
* Add filtering to card printing display.

## 0.1.0

Initial version.
