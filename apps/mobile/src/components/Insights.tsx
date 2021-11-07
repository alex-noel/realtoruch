import React, { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import Svg, { Line, Path, Circle, Text as SvgText } from "react-native-svg";
import { api } from "../api";
import { History } from "../types";
import { c, s } from "../theme";
import { Button, Chip, money } from "./UI";

export default function Insights({
  city,
  districts,
}: {
  city: string;
  districts: string[];
}) {
  const [district, setDistrict] = useState("");
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
  const min = Math.min(...points.map((p) => p.median_rent_pln)) * 0.95;
  const max = Math.max(...points.map((p) => p.median_rent_pln)) * 1.05;
  const x = (i: number) => 70 + (i * 660) / Math.max(1, points.length - 1);
  const y = (v: number) => 235 - ((v - min) / (max - min || 1)) * 180;
  const path = points
    .map((p, i) => `${i ? "L" : "M"} ${x(i)} ${y(p.median_rent_pln)}`)
    .join(" ");
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
      ) : !points.length ? (
        <Text style={s.text}>
          No observations for this area yet. Historical data will appear as
          sources are connected.
        </Text>
      ) : (
        <>
          <View style={[s.row, { flexWrap: "wrap", gap: 16 }]}>
            {[
              ["MEDIAN BASE RENT", money(latest!.median_rent_pln)],
              ["PER SQUARE METER", `${money(latest!.median_per_m2)} / m²`],
              ["HOMES IN LATEST SAMPLE", String(latest!.sample_size)],
              [
                "CHANGE IN THIS PERIOD",
                `${((latest!.median_rent_pln / first.median_rent_pln - 1) * 100).toFixed(1)}%`,
              ],
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
            <View
              style={[
                s.row,
                { justifyContent: "space-between", flexWrap: "wrap", gap: 8 },
              ]}
            >
              <Text style={[s.text, { fontWeight: "600" }]}>
                Monthly median asking rent
              </Text>
              {points.some((p) => p.is_demo) && (
                <Text style={[s.label, { color: c.warning }]}>
                  ILLUSTRATIVE DATA
                </Text>
              )}
            </View>
            <Svg
              viewBox="0 0 800 290"
              width="100%"
              height={290}
              accessibilityLabel="Monthly median base rent chart"
              role="img"
            >
              {[0, 1, 2, 3].map((i) => {
                const value = min + ((max - min) * i) / 3;
                return (
                  <React.Fragment key={i}>
                    <Line
                      x1={65}
                      y1={y(value)}
                      x2={745}
                      y2={y(value)}
                      stroke={c.line}
                      strokeDasharray="3 5"
                    />
                    <SvgText
                      x={54}
                      y={y(value) + 4}
                      textAnchor="end"
                      fontSize={10}
                      fill={c.muted}
                    >
                      {Math.round(value)}
                    </SvgText>
                  </React.Fragment>
                );
              })}
              <Path
                d={`${path} L ${x(points.length - 1)} 235 L 70 235 Z`}
                fill="#E9EEE4"
              />
              <Path d={path} fill="none" stroke={c.green} strokeWidth={3} />
              {points.map((p, i) => (
                <React.Fragment key={p.month}>
                  <Circle
                    cx={x(i)}
                    cy={y(p.median_rent_pln)}
                    r={4}
                    fill={c.green}
                  />
                  <SvgText
                    x={x(i)}
                    y={264}
                    textAnchor="middle"
                    fontSize={11}
                    fill={c.muted}
                  >
                    {p.month}
                  </SvgText>
                </React.Fragment>
              ))}
            </Svg>
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
                <Text style={s.text}>{p.month}</Text>
                <Text style={s.text}>{money(p.median_rent_pln)}</Text>
                <Text style={s.muted}>
                  {p.sample_size} homes
                  {p.sample_size < 30 ? " · small sample" : ""}
                </Text>
              </View>
            ))}
          </View>
        </>
      )}
    </View>
  );
}
