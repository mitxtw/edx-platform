define([
        'js/commerce/views/receipt_view'
    ],
    function (){
        describe("edx.commerce.ReceiptView", function() {
            var view = null;
            var data;

            beforeEach(function(){
                loadFixtures("js/fixtures/commerce/checkout_receipt.html");

                var receiptFixture = readFixtures("templates/commerce/receipt.underscore");
                appendSetFixtures(
                    "<script id=\"receipt-tpl\" type=\"text/template\" >" + receiptFixture + "</script>"
                );
                data = {
                    "status": "Open",
                    "lines": [
                        {
                            "status": "Open",
                            "unit_price_excl_tax": "10.00",
                            "product": {
                                "attribute_values": [
                                    {
                                        "name": "certificate_type",
                                        "value": "verified"
                                    },
                                    {
                                        "name": "course_key",
                                        "value": "course-v1:edx+dummy+2015_T3"
                                    },
                                    {
                                        "name": "id_verification_required",
                                        "value": true
                                    }
                                ],
                                "stockrecords": [
                                    {
                                        "price_currency": "USD",
                                        "product": 123,
                                        "partner_sku": "86A734B",
                                        "partner": 1,
                                        "price_excl_tax": "10.00",
                                        "id": 123
                                    }
                                ],
                                "product_class": "Seat",
                                "title": "Dummy title",
                                "url": "https://ecom.edx.org/api/v2/products/123/",
                                "price": "10.00",
                                "expires": null,
                                "is_available_to_buy": true,
                                "id": 123,
                                "structure": "child"
                            },
                            "line_price_excl_tax": "10.00",
                            "description": "Seat in Introduction to Water and Climate with verified certificate (and ID verification)",
                            "title": "Seat in Introduction to Water and Climate with verified certificate (and ID verification)",
                            "quantity": 1
                        }
                    ],
                    "number": "EDX-103928",
                    "date_placed": "2016-04-25T09:21:02Z",
                    "currency": "USD",
                    "total_excl_tax": "10.00"
                };
                view = new edx.commerce.ReceiptView({el: $('#receipt-container')});
                view.renderReceipt(data);
            });
            it("sends analytic event when receipt is rendered", function() {
                expect(window.analytics.track).toHaveBeenCalledWith(
                    "Completed Order",
                    {
                        orderId: "EDX-103928",
                        total: "10.00",
                        currency: "USD"
                    }
                );

            });

        });
    }
);
