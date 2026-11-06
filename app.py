import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from database import build_db, query, DB_FILE, TIME_BANDS

# Set up SQLite the first time the app runs.
build_db()

# The time bands in the right order (used for the graphs).
band_order = list(TIME_BANDS.values())


# ---------- Database functions ----------

def change_db(sql, values=()):
    # query() in database.py only reads, so this one saves changes (insert/update/delete).
    con = sqlite3.connect(DB_FILE)
    try:
        con.execute(sql, values)
        con.commit()
    finally:
        con.close()


def get_all_records():
    return query("SELECT id, country, time_band, mean_score, standard_error "
                 "FROM pisa_math ORDER BY country, id")


def filter_records(country, band):
    # Start with all records, then apply whichever filters the user selected.
    sql = "SELECT id, country, time_band, mean_score, standard_error FROM pisa_math"
    conditions = []
    values = []

    if country != "All countries":
        conditions.append("country = ?")
        values.append(country)

    if band != "All time bands":
        conditions.append("time_band = ?")
        values.append(band)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    return query(sql + " ORDER BY country, id", values)


def add_record(country, band, score, error):
    # Stops and shows an error if something is missing.
    if country.strip() == "":
        st.error("Please enter a country.")
        return

    try:
        change_db("""
            INSERT INTO pisa_math
                (country, time_band, mean_score, standard_error, flagged_asterisk)
            VALUES (?, ?, ?, ?, 0)
        """, (country.strip(), band, score, error))
        st.success("Record saved!")
    except sqlite3.IntegrityError:
        # The table has UNIQUE(country, time_band)
        st.error("That country and time band already has a record.")


def update_record(record_id, new_score):
    change_db("UPDATE pisa_math SET mean_score = ? WHERE id = ?", (new_score, record_id))


def delete_record(record_id):
    change_db("DELETE FROM pisa_math WHERE id = ?", (record_id,))


def get_average_by_time_band():
    rows = query("SELECT time_band, AVG(mean_score) FROM pisa_math GROUP BY time_band")

    # Put them in the same order as the time bands.
    averages = {}
    for band, avg in rows:
        averages[band] = avg

    result = []
    for band in band_order:
        if band in averages:
            result.append((band, averages[band]))
    return result


def get_average_by_country(country):
    rows = query("SELECT AVG(mean_score) FROM pisa_math WHERE country = ?", (country,))
    return rows[0][0]


def make_table(records):
    # Give the table readable column headings.
    table = []
    for record_id, country_name, time_band, score, error in records:
        table.append({
            "ID": record_id,
            "Country": country_name,
            "Time band": time_band,
            "Mean maths score": score,
            "Standard error": error,
        })
    return table


# ---------- Page ----------

st.title("Device Time and Maths Scores")
st.write("Explore PISA 2022 maths scores by country and time spent on digital devices at school.")

# Get the country names from SQLite for the dropdowns.
rows = query("SELECT DISTINCT country FROM pisa_math ORDER BY country")
countries = [row[0] for row in rows]

page = st.sidebar.radio("Menu", ["View Data", "Add Record", "Edit or Delete", "Averages", "Graphs"])


# ---------- View Data ----------
if page == "View Data":
    country = st.selectbox("Choose a country", ["All countries"] + countries)
    band = st.selectbox("Choose a time band", ["All time bands"] + band_order)

    records = filter_records(country, band)

    st.write(f"{len(records)} matching records")
    st.dataframe(make_table(records), hide_index=True)


# ---------- Add Record ----------
elif page == "Add Record":
    st.subheader("Add a new record")

    new_country = st.text_input("Country")
    new_band = st.selectbox("Time band", band_order)
    new_score = st.number_input("Mean maths score", min_value=0.0, max_value=1000.0, value=400.0)
    new_error = st.number_input("Standard error", min_value=0.0, max_value=100.0, value=0.0)

    if st.button("Submit"):
        add_record(new_country, new_band, new_score, new_error)


# ---------- Edit or Delete ----------
elif page == "Edit or Delete":
    st.subheader("Edit or delete a record")

    country = st.selectbox("Choose a country", countries)
    records = filter_records(country, "All time bands")

    # Let the user pick a record by its time band.
    ids = [record[0] for record in records]
    labels = {}
    for record in records:
        labels[record[0]] = f"{record[2]} (score {record[3]})"

    chosen_id = st.selectbox("Choose a record", ids, format_func=lambda i: labels[i])
    new_score = st.number_input("New mean score", min_value=0.0, max_value=1000.0, value=400.0)

    if st.button("Update"):
        update_record(chosen_id, new_score)
        st.success("Record updated!")

    if st.button("Delete"):
        delete_record(chosen_id)
        st.success("Record deleted!")

    # Show the table again so the changes are visible.
    st.dataframe(make_table(filter_records(country, "All time bands")), hide_index=True)


# ---------- Averages ----------
elif page == "Averages":
    st.subheader("Average score for each time band")

    averages = get_average_by_time_band()
    table = []
    for band, avg in averages:
        table.append({"Time band": band, "Average score": round(avg, 1)})
    st.dataframe(table, hide_index=True)

    st.subheader("Average score for a country")
    country = st.selectbox("Choose a country", countries)
    country_avg = get_average_by_country(country)
    st.write(f"{country} has an average score of {round(country_avg, 1)}")


# ---------- Graphs ----------
elif page == "Graphs":
    st.subheader("Average score for each time band")

    averages = get_average_by_time_band()
    bar_data = pd.DataFrame(averages, columns=["Time band", "Average score"])

    bar_chart = alt.Chart(bar_data).mark_bar().encode(
        x=alt.X("Time band", sort=band_order),
        y="Average score"
    )
    st.altair_chart(bar_chart)

    st.subheader("Compare countries")
    chosen = st.multiselect("Pick countries to compare", countries, default=countries[:2])

    if len(chosen) == 0:
        st.write("Pick at least one country to see the graph.")
    else:
        line_rows = []
        for name in chosen:
            for record in filter_records(name, "All time bands"):
                line_rows.append({"Country": name, "Time band": record[2], "Score": record[3]})

        line_data = pd.DataFrame(line_rows)

        line_chart = alt.Chart(line_data).mark_line(point=True).encode(
            x=alt.X("Time band", sort=band_order),
            y=alt.Y("Score", scale=alt.Scale(zero=False)),
            color="Country"
        )
        st.altair_chart(line_chart)