import React, { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import Svg, { Line, Path, Circle, Text as SvgText } from "react-native-svg";
import { api } from "../api";
import { History } from "../types";
import { c, s } from "../theme";
import { Button, Chip, money } from "./UI";

const MONTH = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
const PERCENT = new Intl.NumberFormat("en-GB", {
  style: "percent",
  signDisplay: "exceptZero",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const SMALL_SAMPLE = 30;

function monthOrdinal(month: string) {
  const [year, number] = month.split("-").map(Number);
  return year * 12 + number - 1;
}

function monthLabel(ordinal: number) {
  return MONTH.format(new Date(Date.UTC(Math.floor(ordinal / 12), ordinal % 12, 1)));
}

type InsightsProps = {
  city: string;
  districts: string[];
};

export default function Insights(props: InsightsProps) {
  return <CityInsights key={props.city} {...props} />;
}

function CityInsights({
  city,
  districts,
}: InsightsProps) {
  const [selectedDistrict, setDistrict] = useState("");
  const district = districts.includes(selectedDistrict) ? selectedDistrict : "";
  const [data, setData] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    api
      .history(city, district)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [city, district, retry]);
  const points = data?.points || [];
  const latest = points.at(-1);
  const first = points[0];
  const canCompare = latest && latest.month !== first.month && first.median_rent_pln > 0;
  const change = canCompare ? PERCENT.format(latest.median_rent_pln / first.median_rent_pln - 1) : null;
  const illustrative = points.some((point) => point.is_demo);
  const smallSamples = points.some((point) => point.sample_size < SMALL_SAMPLE);
  return (
    <View style={{ gap: 24 }}>
      <View>
        <Text style={s.label}>KNOW YOUR NEIGHBORHOOD</Text>
        <Text style={[s.title, { marginTop: 12, fontSize: 36 }]}>
          A little perspective on price.
        </Text>
        <Text style={[s.muted, { marginTop: 12 }]}>
          Observed asking rents in {city}. Duplicate adverts count as one home.
        </Text>
      </View>
      <View style={[s.row, { flexWrap: "wrap", gap: 8 }]}>
        {["", ...districts].map((d) => (
          <Chip
            key={d}
            label={d || "Whole city"}
            selected={district === d}
            onPress={() => setDistrict(d)}
          />
        ))}
      </View>
      {error ? (
        <View style={{ gap: 12 }}>
          <Text accessibilityRole="alert" style={s.text}>
            {error}
          </Text>
          <Button onPress={() => setRetry(retry + 1)}>Try again</Button>
        </View>
      ) : !data ? (
        <ActivityIndicator color={c.green} />
      ) : !latest ? (
        <Text style={s.text}>
          No observations for this area yet. Historical data will appear as
          sources are connected.
        </Text>
      ) : (
        <>
          {(illustrative || smallSamples) && (
            <View style={{ backgroundColor: c.cream, padding: 14, gap: 4 }}>
              {illustrative && <Text style={[s.text, { fontWeight: "600" }]}>Includes illustrative data</Text>}
              {smallSamples && <Text style={s.text}>Some months have fewer than {SMALL_SAMPLE} observed homes.</Text>}
            </View>
          )}
          <View style={[s.row, { flexWrap: "wrap", gap: 16 }]}>
            {[
              ["LATEST MEDIAN BASE RENT", money(latest.median_rent_pln)],
              ["LATEST MEDIAN PER SQUARE METER", `${money(latest.median_per_m2)} / m²`],
              ["HOMES IN LATEST SAMPLE", String(latest.sample_size)],
              ...(change === null ? [] : [["CHANGE IN OBSERVED SAMPLE MEDIANS", change]]),
            ].map(([label, value]) => (
              <View
                key={label}
                style={[
                  s.card,
                  { padding: 22, minWidth: 180, flex: 1, gap: 12 },
                ]}
              >
                <Text style={[s.label, { fontSize: 9 }]}>{label}</Text>
                <Text style={s.title}>{value}</Text>
              </View>
            ))}
          </View>
          <View style={[s.card, { padding: 24, gap: 18 }]}>
            <Text accessibilityRole="header" style={[s.text, { fontWeight: "600" }]}>
              Monthly median asking rent
            </Text>
            <Text style={s.text}>
              {points.length === 1
                ? `${monthLabel(monthOrdinal(latest.month))} · One observed month · ${money(latest.median_rent_pln)}`
                : `${monthLabel(monthOrdinal(first.month))} to ${monthLabel(monthOrdinal(latest.month))} · ${points.length} observed months · ${money(first.median_rent_pln)} to ${money(latest.median_rent_pln)}`}
            </Text>
            {change !== null && <Text style={s.muted}>The homes in the monthly samples can vary.</Text>}
            <RentChart points={points} />
            <Text style={s.muted}>{data.methodology}</Text>
          </View>
          <View style={[s.card, { padding: 22, gap: 10 }]}>
            <Text style={[s.text, { fontWeight: "600" }]}>
              The numbers behind the line
            </Text>
            {points.map((p) => (
              <View
                key={p.month}
                style={[
                  s.row,
                  {
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: 8,
                    paddingVertical: 9,
                    borderTopWidth: 1,
                    borderColor: c.line,
                  },
                ]}
              >
                <Text style={s.text}>{monthLabel(monthOrdinal(p.month))}</Text>
                <Text style={s.text}>{money(p.median_rent_pln)}</Text>
                <Text style={s.muted}>
                  {p.sample_size} homes
                  {p.sample_size < SMALL_SAMPLE ? " · small sample" : ""}
                </Text>
              </View>
            ))}
          </View>
        </>
      )}
    </View>
  );
}

const CHART_HEIGHT = 180;
const PLOT_TOP = 16;
const PLOT_BOTTOM = 144;

function RentChart({ points }: { points: History["points"] }) {
  const [width, setWidth] = useState(0);
  const left = 76;
  const right = Math.max(left + 1, width - 4);
  const plotWidth = right - left;
  const months = points.map((point) => monthOrdinal(point.month));
  const firstMonth = months[0];
  const monthSpan = months[months.length - 1] - firstMonth;
  const x = (month: number) => monthSpan
    ? left + ((month - firstMonth) / monthSpan) * plotWidth
    : left + plotWidth / 2;
  const rents = points.map((point) => point.median_rent_pln);
  const min = Math.min(...rents);
  const max = Math.max(...rents);
  const y = (rent: number) => max === min
    ? (PLOT_TOP + PLOT_BOTTOM) / 2
    : PLOT_BOTTOM - ((rent - min) / (max - min)) * (PLOT_BOTTOM - PLOT_TOP);
  const grid = min === max ? [min] : [min, max];
  const tickCount = Math.min(monthSpan + 1, Math.max(2, Math.min(5, Math.floor(plotWidth / 90) + 1)));
  const ticks = Array.from({ length: tickCount }, (_, index) =>
    firstMonth + Math.round((index * monthSpan) / Math.max(1, tickCount - 1)));
  const path = points.map((point, index) => {
    const adjacent = index > 0 && months[index] === months[index - 1] + 1;
    return `${adjacent ? "L" : "M"}${x(months[index])} ${y(point.median_rent_pln)}`;
  }).join(" ");

  return (
    <View
      style={{ height: CHART_HEIGHT }}
      onLayout={({ nativeEvent }) => setWidth(Math.floor(nativeEvent.layout.width))}
    >
      {width > left && (
        <Svg
          viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
          width="100%"
          height={CHART_HEIGHT}
          accessibilityLabel="Monthly median asking rent chart"
          role="img"
        >
          {grid.map((value) => (
            <React.Fragment key={value}>
              <Line x1={left} y1={y(value)} x2={right} y2={y(value)} stroke={c.line} strokeDasharray="3 5" />
              <SvgText x={left - 8} y={y(value) + 4} textAnchor="end" fontSize={12} fill={c.muted}>
                {money(value)}
              </SvgText>
            </React.Fragment>
          ))}
          <Path d={path} fill="none" stroke={c.green} strokeWidth={2} />
          {points.map((point, index) => (
            <Circle key={point.month} cx={x(months[index])} cy={y(point.median_rent_pln)} r={3} fill={c.green} />
          ))}
          {ticks.map((month, index) => (
            <SvgText
              key={month}
              x={x(month)}
              y={168}
              textAnchor={ticks.length === 1 ? "middle" : index === 0 ? "start" : index === ticks.length - 1 ? "end" : "middle"}
              fontSize={12}
              fill={c.muted}
            >
              {monthLabel(month)}
            </SvgText>
          ))}
        </Svg>
      )}
    </View>
  );
}
