set -ex

for num in `seq 2003 2016`
do
    python parser.py "$num" < "csvs/${num}_raw.csv" > "csvs/${num}.csv"
done
