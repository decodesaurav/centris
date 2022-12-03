# -*- coding: utf-8 -*-
import scrapy
from scrapy.selector import Selector
from scrapy_splash import SplashRequest
import json


class ListingsSpider(scrapy.Spider):
    name = 'listings'
    allowed_domains = ['www.centris.ca']

    handle_httpstatus_list = [555]

    position = {
        "startPosition": 0
    }

    script = '''
        function main(splash, args)
        splash:on_request(function(request)
            if request.url:find('css') then
                request.abort()
            end
        end)
        splash.js_enabled = false
        splash.images_enabled = false
        assert(splash:go(args.url))
        assert(splash:wait(0.5))
        return splash:html()
end
    '''
# STARTING THE SESSION

    def start_requests(self):
        yield scrapy.Request(
            url='https://www.centris.ca/UserContext/Lock',
            method="POST",
            body=json.dumps({
                "uc": 0
            }),
            headers={
                'Content-Type': 'application/json'
            },
            callback=self.lock,
        )
# lOCK FOLLOWED BY UNLOCK

    def lock(self, response):
        uck = response.text
        yield scrapy.Request(
            url='https://www.centris.ca/UserContext/UnLock',
            method='POST',
            body=json.dumps({
                'uc': 0,
                'uck': uck
            }),
            headers={
                'Content-Type': 'application/json',
                'x-centric-uck': uck,
                'x-centris-uc': 0
            },
            callback=self.send_query,
            meta={
                'uck': uck
            }
        )
# SENDING THE QUERY AFTER UNLOCK

    def send_query(self, response):
        uck = response.meta['uck']
        # REQUEST PAYLOAD IN JSON
        query = {
            "query": {
                "UseGeographyShapes": 0,
                "Filters": [
                    {
                        "MatchType": "CityDistrictAll",
                        "Text": "Montréal (All boroughs)",
                        "Id": 5
                    }
                ],
                "FieldsValues": [
                    {
                        "fieldId": "CityDistrictAll",
                        "value": 5,
                        "fieldConditionId": "",
                        "valueConditionId": ""
                    },
                    {
                        "fieldId": "Category",
                        "value": "Residential",
                        "fieldConditionId": "",
                        "valueConditionId": ""
                    },
                    {
                        "fieldId": "SellingType",
                        "value": "Rent",
                        "fieldConditionId": "",
                        "valueConditionId": ""
                    },
                    {
                        "fieldId": "LandArea",
                        "value": "SquareFeet",
                        "fieldConditionId": "IsLandArea",
                        "valueConditionId": ""
                    },
                    {
                        "fieldId": "RentPrice",
                        "value": 0,
                        "fieldConditionId": "ForRent",
                        "valueConditionId": ""
                    },
                    {
                        "fieldId": "RentPrice",
                        "value": 1500,
                        "fieldConditionId": "ForRent",
                        "valueConditionId": ""
                    }
                ]
            },
            "isHomePage": True
        }

        yield scrapy.Request(
            url="https://www.centris.ca/property/UpdateQuery",
            method="POST",
            body=json.dumps(query),
            headers={
                "Content-Type": "application/json",
                "x-centris-uck": uck,
                "x-centris-uc": 0
            },
            callback=self.update_query
        )
    # GETTING THE HTML VALUE OF THE WEBSITE FROM THE GETINSCRIPTION AND
    # SETTING THE STARTING POINT AS THE GLOBAL VARIABLE

    def update_query(self, response):
        yield scrapy.Request(
            url="https://www.centris.ca/Property/GetInscriptions",
            method="POST",
            body=json.dumps(self.position),
            headers={
                "Content-Type": 'application/json',
            },
            callback=self.parse
        )

    def parse(self, response):
        # CONVERTING THE JSON OBJECT IN PYTHON DICT
        resp_dict = json.loads(response.body)
        # GETITNG THE HTML FROM THE REQUEST PAYLOAD
        html = resp_dict.get('d').get('Result').get('html')
        sel = Selector(text=html)
        listings = sel.xpath("//div[@class='shell']")
        for listing in listings:
            category = listing.xpath(
                ".//span[@class='category']/div/text()").get()
            features_bed = listing.xpath(".//div[@class='sdb']/text()").get()
            features_bathroom = listing.xpath(".//div[@class='cac']/text()").get()
            price = listing.xpath(
                ".//div[@class='price']/span[1]/text()").get()
            city = listing.xpath(
                ".//span[@class='address']/div[1]/text()").get()
            url = listing.xpath(
                ".//div[@class='thumbnail property-thumbnail-feature legacy-reset']/a/@href").get()
            abs_url = f"https://www.centris.ca{url}"

            yield SplashRequest(
                url= abs_url,
                endpoint = 'execute',
                callback= self.parse_summary,
                args={
                    'lua_source' : self.script
                },
                meta={
                    'cat': category,
                    'fea-bed': features_bed,
                    'fea-bath': features_bathroom,
                    'pri':price,
                    'city': city,
                    'url': abs_url
                }
            )
        count = resp_dict.get('d').get('Result').get('count')
        increment_number = resp_dict.get('d').get(
            'Result').get('inscNumberPerPage')

        if self.position['startPosition'] <= count:
            self.position['startPosition'] += increment_number
            yield scrapy.Request(
                url="https://www.centris.ca/Property/GetInscriptions",
                method="POST",
                body=json.dumps(self.position),
                headers={
                    'Content-Type': 'application/json'
                },
                callback=self.parse
            )
    def parse_summary(self,response):
        address = response.xpath("//h2[@itemprop='address']/text()").get()
        description = response.xpath("//div[@itemprop='description']/text()").get()
        category = response.request.meta['cat']
        features_bed = response.request.meta['fea-bed']
        features_bath = response.request.meta['fea-bath']
        price = response.request.meta['pri']
        city = response.request.meta['city']
        url = response.request.meta['url']

        yield{
            'address': address,
            'description': description,
            'category': category,
            'features_bed': features_bed,
            'features_bath': features_bath,
            'price': price,
            'city': city,
            'url': url
        }