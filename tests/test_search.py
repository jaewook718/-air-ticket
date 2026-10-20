import unittest
from datetime import date, timedelta
from unittest.mock import patch
from air_ticket.main import search, search_dates, live_offers


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.monday = date.today() + timedelta(days=7 - date.today().weekday())
        self.data = dict(origin='ICN', destination='NRT', start=self.monday.isoformat(),
                         end=(self.monday + timedelta(days=7)).isoformat(), min_nights=3,
                         max_nights=4, adults=2, budget=500000, weekend='any', direct=False, mode='sample')

    def test_date_combinations_are_complete_and_bounded(self):
        pairs = search_dates(self.data)[-1]
        self.assertEqual(len(pairs), 9)
        self.assertTrue(all(back <= self.data['end'] for _, back, _, _ in pairs))

    def test_weekend_filters_partition_dates(self):
        all_pairs = search_dates(self.data)[-1]
        weekend = search_dates(dict(self.data, weekend='include'))[-1]
        weekday = search_dates(dict(self.data, weekend='exclude'))[-1]
        self.assertEqual(len(all_pairs), len(weekend) + len(weekday))
        self.assertTrue(weekend and weekday)
        self.assertTrue(all(p[3] for p in weekend))
        self.assertFalse(any(p[3] for p in weekday))

    def test_direct_budget_and_sort(self):
        result = search(dict(self.data, budget=300000, direct=True))
        self.assertTrue(result['offers'])
        prices = [o['price'] for o in result['offers']]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(all(o['price'] <= 600000 and o['stops'] == 0 for o in result['offers']))
        self.assertEqual(result['source'], 'sample')

    def test_no_results_is_valid(self):
        self.assertEqual(search(dict(self.data, budget=1))['offers'], [])

    def test_too_many_combinations_rejected(self):
        with self.assertRaisesRegex(ValueError, '조합'):
            search(dict(self.data, end=(self.monday+timedelta(days=60)).isoformat()))

    def test_invalid_input(self):
        for change in ({'destination':'ICN'}, {'min_nights':5, 'max_nights':3},
                       {'adults':0}, {'weekend':'bogus'}, {'start':'invalid'}, {'direct':'false'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                search(dict(self.data, **change))

    @patch.dict('os.environ', {}, clear=True)
    def test_live_without_keys_is_not_sample_fallback(self):
        with self.assertRaisesRegex(ValueError, 'AMADEUS_CLIENT_ID'):
            search(dict(self.data, mode='live'))

    @patch.dict('os.environ', {'AMADEUS_CLIENT_ID':'test', 'AMADEUS_CLIENT_SECRET':'test'}, clear=True)
    @patch('air_ticket.main.api_json')
    def test_provider_mapping_and_overnight_return(self, api):
        departure = self.monday.isoformat()
        back = (self.monday+timedelta(days=3)).isoformat()
        arrival = (self.monday+timedelta(days=4)).isoformat()
        api.side_effect = [{'access_token':'test-token'}, {'data':[{
            'id':'1', 'price':{'grandTotal':'480001.2'}, 'itineraries':[
                {'duration':'PT2H', 'segments':[{'carrierCode':'ZZ', 'departure':{'at':departure+'T10:00:00'}, 'arrival':{'at':departure+'T12:00:00'}}]},
                {'duration':'PT3H', 'segments':[{'carrierCode':'ZZ', 'departure':{'at':back+'T23:00:00'}, 'arrival':{'at':arrival+'T02:00:00'}}]}
            ]}], 'dictionaries':{'carriers':{'ZZ':'Test Airline'}}}]
        offer = live_offers('ICN', 'NRT', 2, [(departure,back,3,False)], True)[0]
        self.assertEqual(offer['price'],480002)
        self.assertEqual(offer['trip_days'],5)
        self.assertEqual(offer['nights'],3)
        self.assertEqual(offer['carrier'],'Test Airline')
        self.assertIn('nonStop=true', api.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
