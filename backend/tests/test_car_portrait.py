from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from backend.app.car_portrait import (
    VehicleTripSample,
    build_active_time_bins,
    build_car_portrait_payload,
    build_region_radar,
    build_route_clusters,
    classify_operation_mode,
)


def make_trip(
    trip_id: int,
    *,
    log_date: date,
    start_time: datetime,
    duration_minutes: int = 30,
    distance_km: float = 8.0,
    start_point: tuple[float, float] = (126.6, 45.7),
    end_point: tuple[float, float] = (126.7, 45.8),
    device_id: str = "10001",
) -> VehicleTripSample:
    return VehicleTripSample(
        trip_id=trip_id,
        device_id=device_id,
        log_date=log_date,
        distance_km=distance_km,
        duration_seconds=duration_minutes * 60.0,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=duration_minutes),
        start_point=start_point,
        end_point=end_point,
    )


class CarPortraitTests(unittest.TestCase):
    def test_classify_night_shift(self) -> None:
        mode = classify_operation_mode(
            {
                "total_trips": 40,
                "night_trip_ratio": 0.62,
                "peak_trip_ratio": 0.18,
                "avg_trip_distance_km": 9.2,
                "avg_daily_work_hours": 8.5,
                "hotspot_concentration": 0.22,
                "dominant_shift": "night",
            }
        )
        self.assertEqual("night_shift", mode)

    def test_classify_commuter_peak(self) -> None:
        mode = classify_operation_mode(
            {
                "total_trips": 36,
                "night_trip_ratio": 0.05,
                "peak_trip_ratio": 0.74,
                "avg_trip_distance_km": 7.8,
                "avg_daily_work_hours": 8.2,
                "hotspot_concentration": 0.24,
                "dominant_shift": "morning_peak",
            }
        )
        self.assertEqual("commuter_peak", mode)

    def test_classify_long_haul(self) -> None:
        mode = classify_operation_mode(
            {
                "total_trips": 28,
                "night_trip_ratio": 0.12,
                "peak_trip_ratio": 0.28,
                "avg_trip_distance_km": 18.4,
                "avg_daily_work_hours": 9.4,
                "hotspot_concentration": 0.16,
                "dominant_shift": "daytime",
            }
        )
        self.assertEqual("long_haul", mode)

    def test_classify_local_shuttle(self) -> None:
        mode = classify_operation_mode(
            {
                "total_trips": 54,
                "night_trip_ratio": 0.08,
                "peak_trip_ratio": 0.32,
                "avg_trip_distance_km": 3.6,
                "avg_daily_work_hours": 7.4,
                "hotspot_concentration": 0.44,
                "dominant_shift": "daytime",
            }
        )
        self.assertEqual("local_shuttle", mode)

    def test_classify_steady_all_day(self) -> None:
        mode = classify_operation_mode(
            {
                "total_trips": 44,
                "night_trip_ratio": 0.18,
                "peak_trip_ratio": 0.36,
                "avg_trip_distance_km": 8.9,
                "avg_daily_work_hours": 11.2,
                "hotspot_concentration": 0.23,
                "dominant_shift": "mixed",
            }
        )
        self.assertEqual("steady_all_day", mode)

    def test_active_time_bins_aggregate_counts_and_share(self) -> None:
        trips = [
            make_trip(1, log_date=date(2025, 1, 1), start_time=datetime(2025, 1, 1, 1, 10), distance_km=10.0),
            make_trip(2, log_date=date(2025, 1, 1), start_time=datetime(2025, 1, 1, 13, 30), distance_km=6.0),
        ]

        bins = build_active_time_bins(trips)
        lookup = {item.label: item for item in bins}
        self.assertEqual(1, lookup["00-02"].trip_count)
        self.assertEqual(10.0, lookup["00-02"].distance_km)
        self.assertEqual(0.5, lookup["00-02"].share_ratio)
        self.assertEqual(1, lookup["12-14"].trip_count)
        self.assertEqual(6.0, lookup["12-14"].distance_km)

    def test_region_radar_assigns_compass_buckets(self) -> None:
        trips = [
            make_trip(
                1,
                log_date=date(2025, 1, 1),
                start_time=datetime(2025, 1, 1, 8, 0),
                start_point=(0.0, 1.0),
                end_point=(1.0, 0.0),
            ),
            make_trip(
                2,
                log_date=date(2025, 1, 1),
                start_time=datetime(2025, 1, 1, 9, 0),
                start_point=(0.0, -1.0),
                end_point=(-1.0, 0.0),
            ),
        ]

        radar, hotspot = build_region_radar(trips)
        lookup = {item.region: item for item in radar}
        self.assertEqual(100.0, lookup["north"].score)
        self.assertEqual(100.0, lookup["east"].score)
        self.assertEqual(100.0, lookup["south"].score)
        self.assertEqual(100.0, lookup["west"].score)
        self.assertEqual(0.25, hotspot)

    def test_route_clusters_merge_nearby_od_pairs(self) -> None:
        trips = [
            make_trip(
                1,
                log_date=date(2025, 1, 1),
                start_time=datetime(2025, 1, 1, 7, 0),
                distance_km=12.0,
                start_point=(126.600, 45.700),
                end_point=(126.660, 45.760),
            ),
            make_trip(
                2,
                log_date=date(2025, 1, 1),
                start_time=datetime(2025, 1, 1, 7, 30),
                distance_km=13.0,
                start_point=(126.606, 45.704),
                end_point=(126.667, 45.763),
            ),
            make_trip(
                3,
                log_date=date(2025, 1, 1),
                start_time=datetime(2025, 1, 1, 18, 0),
                distance_km=8.0,
                start_point=(126.820, 45.820),
                end_point=(126.910, 45.910),
            ),
        ]

        clusters = build_route_clusters(trips)
        self.assertGreaterEqual(len(clusters), 2)
        self.assertEqual(2, clusters[0].trip_count)
        self.assertAlmostEqual(12.5, clusters[0].avg_distance_km, places=2)

    def test_build_portrait_payload_handles_small_sample(self) -> None:
        trips = [
            make_trip(
                1,
                log_date=date(2025, 1, 1),
                start_time=datetime(2025, 1, 1, 9, 0),
                distance_km=5.0,
            )
        ]

        portrait = build_car_portrait_payload("10001", trips, peer_groups=[])
        self.assertIsNotNone(portrait)
        assert portrait is not None
        self.assertEqual(1, portrait.summary.total_trips)
        self.assertEqual([], portrait.route_clusters)
        self.assertEqual([], portrait.peer_groups)

    def test_build_portrait_payload_returns_none_without_trips(self) -> None:
        self.assertIsNone(build_car_portrait_payload("10001", [], peer_groups=[]))


if __name__ == "__main__":
    unittest.main()
