import time
import re
import requests
import logging
from bs4 import BeautifulSoup
import functools

if __name__ == "__main__":
    # logging setup
    logging.basicConfig(level=logging.INFO)

    # request main page
    r = requests.get("https://de.wikipedia.org/wiki/Liste_der_Kfz-Kennzeichen_in_Deutschland")

    if r.status_code != 200:
        logging.error("wikipedia request status code {}".format(r.status_code))
        exit(1)

    soup = BeautifulSoup(r.text, 'html.parser')

    # get all tables in "Liste der Kfz-Kennzeichen in Deutschland"

    # table names
    # letters <- ["A", ..., "Z", "0-9"]
    letters = [chr(64 + i) for i in range(1, 27)]
    letters.append("0–9")  # watch out! the – is not a - for some reason?

    all_rows = list()

    # parse tables
    for letter in letters:
        logging.info("scraping letter {}".format(letter))
        occurrences = soup.find_all(id=letter)[0]
        table = occurrences.parent.next_sibling.next_sibling

        rowspan = 0
        row_content = {
            "abk": "",  # abkürzung
            "abg": "",  # ableitung
            "land": "",  # bundesland
            "link": "",  # link for coordinates
            "coords": (0, 0),  # coordinates
            "sl": [],  # stadt/landkreis
            "links": []  # all links
        }
        for tr in table.find_all("tr")[1:]:
            cols = tr.find_all("td")


            # typecheck for BeautifulSoups get_text()
            def get_text(obj):
                if isinstance(obj, str):
                    return obj
                # some replacements for convenience
                return re.sub("\\[[0-9]\\]", "", obj.get_text().replace("\n", "").replace("\xa0", " "))


            def get_title_href_tuple(link_soup):  # extract links
                if "title" in link_soup.attrs:
                    return link_soup["title"], link_soup["href"]
                return get_text(link_soup), link_soup["href"]


            if rowspan > 0:  # row is associated to previous
                row_content["sl"].append(get_text(cols[0]))
                for link in cols[0].find_all("a"):
                    row_content["links"].append(get_title_href_tuple(link))
                rowspan -= 1  # decrement rowspan
            else:  # row is NOT associated to previous
                abkürzung = cols[0]
                kreis = cols[1]

                if len(cols) >= 3:  # special case
                    ableitung = cols[2]
                else:
                    ableitung = ""

                if len(cols) >= 4:  # special case
                    bundesland = cols[3]
                else:
                    bundesland = "bundesweit"

                if "rowspan" in abkürzung.attrs:  # row starts a rowspan
                    rowspan = int(abkürzung["rowspan"]) - 1

                # get data
                row_content["abk"] = get_text(abkürzung)
                row_content["abg"] = get_text(ableitung)
                row_content["land"] = get_text(bundesland)
                row_content["sl"].append(get_text(kreis))
                row_content["link"] = kreis.find_all("a")[0]["href"]

                # extract all links
                for link in abkürzung.find_all("a"):
                    row_content["links"].append(get_title_href_tuple(link))
                for link in kreis.find_all("a"):
                    row_content["links"].append(get_title_href_tuple(link))
                if len(cols) >= 3:  # special case
                    for link in ableitung.find_all("a"):
                        row_content["links"].append(get_title_href_tuple(link))
                if len(cols) >= 4:  # special case
                    for link in bundesland.find_all("a"):
                        row_content["links"].append(get_title_href_tuple(link))

                # get coords
                if row_content["link"]:
                    r_c = requests.get("https://de.wikipedia.org{}".format(row_content["link"]))
                    if r_c.status_code != 200:
                        logging.warning(
                            "code {} for {} link {}".format(r_c.status_code, row_content["abk"], row_content["link"]))
                    else:
                        soup_c = BeautifulSoup(r_c.text, 'html.parser')
                        geourls = soup_c.find_all("a", href=re.compile("geohack.toolforge.org"))
                        # extract coords if they exist
                        if len(geourls) >= 1:
                            coords = str(geourls[0]).split("params=")[1].split("_E_")[0].split("_N_")
                            row_content["coords"] = (float(coords[0]), float(coords[1]))
                    time.sleep(1.01)  # :)

            if rowspan == 0:  # no associated rows following
                # add to full list
                all_rows.append(row_content.copy())
                # write
                with open("kennzeichendb.csv", "a", encoding="utf-8") as f:
                    f.write(functools.reduce(lambda xs, x: xs + ";" + str(x), row_content.values(), "")[1:] + "\n")
                # reset row_content
                row_content["sl"] = list()
                row_content["link"] = ""
                row_content["coords"] = (0, 0)
                row_content["links"] = list()

    logging.info("total: {}".format(len(all_rows)))
