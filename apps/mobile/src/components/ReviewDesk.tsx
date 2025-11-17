import React, { useEffect, useState } from "react";
import { Linking, Text, View } from "react-native";
import { market, Report } from "../marketplaceApi";
import { s } from "../theme";
import { Button, Field, money } from "./UI";
import type { RentalDeskWork } from "./MarketplaceDialog";

export interface ReviewDeskProps extends RentalDeskWork {}

export function ReviewDesk({ run, busy }: ReviewDeskProps) {
  const [reports, setReports] = useState<Report[]>([]);
  const [reason, setReason] = useState("");
  const [identity, setIdentity] = useState<{
    id: string;
    data: Awaited<ReturnType<typeof market.identity>>;
  } | null>(null);
  async function reload() {
    setReports((await market.reports()).items);
  }
  useEffect(() => {
    run(reload);
  }, []);
  return (
    <>
      <Text style={s.muted}>
        Review source evidence before acting. Every decision is recorded. Hidden
        homes stay hidden when sources are collected again.
      </Text>
      <Field
        label="REVIEW REASON (REQUIRED FOR EACH DECISION)"
        multiline
        value={reason}
        onChange={setReason}
      />
      {reports.length === 0 && <Text style={s.text}>No pending reports.</Text>}
      {reports.map((report) => (
        <View key={report.id} style={[s.card, { padding: 20, gap: 12 }]}>
          <Text style={[s.title, { fontSize: 19 }]}>
            {report.listing.title}
          </Text>
          <Text style={s.text}>{report.reason}</Text>
          <Text style={s.muted}>
            {report.listing.address} · {report.listing.city} ·{" "}
            {report.hidden ? "Hidden" : "Visible"}
          </Text>
          <Text style={s.text}>{report.listing.description}</Text>
          <Button
            outline
            disabled={busy}
            onPress={() =>
              run(async () => {
                setIdentity({
                  id: report.listing.id,
                  data: await market.identity(report.listing.id),
                });
              })
            }
          >
            Review duplicate identity
          </Button>
          {identity?.id === report.listing.id && (
            <View style={{ gap: 12 }}>
              <Text style={s.muted}>
                Compare the original sources before changing identity. A merge
                retains favorites and seen prices. Separating a source retains
                both homes on existing shortlists.
              </Text>
              {identity.data.sources.map((source) => (
                <View key={source.id} style={{ gap: 8 }}>
                  <Text style={s.text}>
                    {source.name} · {source.address} · {money(source.rent_pln)}
                  </Text>
                  <Button outline onPress={() => Linking.openURL(source.url)}>
                    Open source
                  </Button>
                  {identity.data.sources.length > 1 && (
                    <Button
                      outline
                      disabled={busy || reason.trim().length < 10}
                      onPress={() =>
                        run(async () => {
                          await market.split(
                            report.listing.id,
                            source.id,
                            reason,
                          );
                          setIdentity(null);
                          setReason("");
                          await reload();
                        })
                      }
                    >
                      Separate this source into another home
                    </Button>
                  )}
                </View>
              ))}
              <Text style={s.label}>
                OTHER HOMES WITH SIMILAR SIZE AND ROOM COUNT
              </Text>
              {identity.data.candidates.map((candidate) => (
                <View
                  key={candidate.id}
                  style={[s.card, { padding: 16, gap: 8 }]}
                >
                  <Text style={s.text}>
                    {candidate.title} · {candidate.address} ·{" "}
                    {money(candidate.rent_pln)}
                  </Text>
                  <Text style={s.muted}>
                    {candidate.sources.map((source) => source.name).join(", ")}{" "}
                    · Similarity alone does not prove these are the same home.
                  </Text>
                  <Button
                    outline
                    disabled={busy || reason.trim().length < 10}
                    onPress={() =>
                      run(async () => {
                        await market.merge(
                          report.listing.id,
                          candidate.id,
                          reason,
                        );
                        setIdentity(null);
                        setReason("");
                        await reload();
                      })
                    }
                  >
                    Merge into this home
                  </Button>
                </View>
              ))}
            </View>
          )}
          {report.listing.risk_flags.map((flag) => (
            <Text key={flag.code} style={s.muted}>
              {flag.detail}
            </Text>
          ))}
          <View style={[s.row, { gap: 8, flexWrap: "wrap" }]}>
            {(["hide", "restore", "dismiss"] as const).map((action) => (
              <Button
                key={action}
                outline
                disabled={busy || reason.trim().length < 10}
                onPress={() =>
                  run(async () => {
                    await market.review(report.id, action, reason);
                    setReason("");
                    await reload();
                  })
                }
              >
                {action}
              </Button>
            ))}
          </View>
        </View>
      ))}
    </>
  );
}
