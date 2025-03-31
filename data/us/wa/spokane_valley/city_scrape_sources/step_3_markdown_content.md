<script>jQuery(document).click(function (event) { var target = jQuery(event.target); if (target.attr('src') && target.parents('.image').length && target.parents('.widget').length) { var text = target.attr('title');  if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Image', eventAction: 'Image - ' + text, eventLabel: window.location.href }); } if (target.is('button') || target.hasClass('button') || target.parents().hasClass('button')) { var text = ""; if (target.parents('.button')[0]) { text = target.parents('.button').first().text(); } else if (target.text().length) { text = target.text(); } else if (target.attr('title').length) { text = target.attr('title'); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Button', eventAction: 'Button - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetCustomHtml').length) { ga('send', { hitType: 'event', eventCategory: 'Custom Html', eventAction: 'Custom Html Clicked', eventLabel: window.location.href }); } if (target.parents('.editor').length) { ga('send', { hitType: 'event', eventCategory: 'Editor', eventAction: 'Editor Link Clicked', eventLabel: window.location.href }); } if (target.parents('.GraphicLinks').length) { var text = ""; var targetGraphicLink = target; if (target.hasClass('widgetGraphicLinksLink')) { targetGraphicLink = jQuery(target.children()[0]); } if (targetGraphicLink.hasClass('text')) { text = targetGraphicLink.text(); } else if (targetGraphicLink.attr('src').length) { if (targetGraphicLink.attr('alt').length) { text = targetGraphicLink.attr('alt'); } else { text = targetGraphicLink.attr('src'); } } else { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Graphic Links', eventAction: 'Graphic Link - ' + text, eventLabel: window.location.href }); } if (target.parents('.InfoAdvanced').length) { ga('send', { hitType: 'event', eventCategory: 'Info Advanced', eventAction: 'Info Advanced Clicked', eventLabel: window.location.href }); } if (target.parents('.list').length) { ga('send', { hitType: 'event', eventCategory: 'List', eventAction: 'List Clicked', eventLabel: window.location.href }); } if (target.parents('.megaMenuItem').length || target.parents('.topMenuItem').length) { var megaMenuText = jQuery('.topMenuItem.mouseover').find('span').text(); var breadCrumbs = []; jQuery('.breadCrumbs > li').each(function () {  breadCrumbs.push(this.textContent); }); var pageTitle = breadCrumbs.join('>'); var subTitleText = target.parents('.megaMenuItem').children('.widgetTitle').children().text(); var text = ""; if (pageTitle) { text += pageTitle + " | "; } else { text += document.title + ' - '; } if (target.text() == "" && megaMenuText == "") { text += "N/A"; } else if (target.text().length && megaMenuText.length) { if (megaMenuText == target.text()) { text += megaMenuText; } else { text += megaMenuText + " - " + subTitleText + " - " + target.text(); } } else if (target.text() == "") { text += megaMenuText; } else { text += target.text(); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Mega Menu', eventAction: 'Mega Menu : ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetNewsFlash').length && target.parents('.widgetItem').length) { var text = jQuery(target.parents('.widgetItem')[0]).find('.widgetTitle').children().text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'News Flash', eventAction: 'News Flash - ' + text, eventLabel: window.location.href }); } if (target.hasClass('widgetQuickLinksLink') || target.find('.widgetQuickLinksLink').length) { var text = target.text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Quick Links', eventAction: 'Quick Links - ' + text, eventLabel: window.location.href }); } if (target.attr('src') && target.parents('.cpSlideshow').length) { var text = target.attr('title'); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Slideshow', eventAction: 'Slideshow - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetText').length) { ga('send', { hitType: 'event', eventCategory: 'Text', eventAction: 'Text Link Clicked', eventLabel: window.location.href }); }});</script>  [Skip to Main Content](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#cc5f8c90dc-b4cb-431b-90ee-10648f8df655)   [![Home Page](images/0ad9a8c94aa440cc4df299174e9931c543b1e622fc867ea7277fd0af7847c0ce)](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities)   [City

Home](https://www.spokanevalleywa.gov)   [![Facebook](images/f75fe6b2979150f27a65063a45dbac12cb171f396bc24955a51d5e5defb17ca0)](https://www.facebook.com/CityofSpokaneValley)   [![X](images/d0fe2b098c04be543d26e00ab1bb534b0b5d55a572d8ce33a85fd54e4fbee539)](https://x.com/CityofSV)   [![Instagram](images/bfc2ef8c5004f63148ccd7fd8aaaa4868631322e5348decd83a385f3ae66d6a2)](https://www.instagram.com/cityspokanevalley)   [![YouTube](images/8335cb2aaec79833d44df2341de759285c86be49875c599b70ec9f7b0e600f0d)](https://www.youtube.com/channel/UCoNlPNd0y5U905mvDfEmn7g)  <script defer type="text/javascript" src="/Common/Controls/jquery-ui-1.14.1/jquery-ui.min.js"></script><script defer src="/Areas/Layout/Assets/Scripts/Search.js" type="text/javascript"></script><script defer type="text/javascript"> $(document).ready(function () { try { $(".widgetSearchButton.widgetSearchButton0b507170-a549-4f5f-bc51-9b5f4d5180ba").click(function (e) { e.preventDefault(); if (false||$("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked')) { doWidgetSearch($(this).siblings(".widgetSearchBox").val(), Number(0)); } else { doWidgetSearch($(this).siblings(".widgetSearchBox").val(), 0); } }); $("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").keypress(function (e) { if (window.clipboardData) { if (e.keyCode === 13) { if ($("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked') || false) { doWidgetSearch($(this).val(), Number(0)); } else { doWidgetSearch($(this).val(), 0); } return false; } } else { if (e.which === 13) { if ($("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked') || false) { doWidgetSearch($(this).val(), Number(0)); } else { doWidgetSearch($(this).val(), 0); } return false; } } return true; }); if (true) { var currentRequest = null; var $searchField = $("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").autocomplete({ source: function (request, response) { currentRequest = $.ajax({ url: '/Search/AutoComplete' + ($("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked') || false? '?departmentId=0' : ''), dataType: "json", timeout: 10000, beforeSend: function () { if (currentRequest != null) { currentRequest.abort(); } }, data: { term: request.term, }, success: function (data) { response(data); $('.autoCompleteError').remove(); }, error: function (xmlhttprequest, textstatus, message) { if (textstatus === "timeout") { if ($("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").siblings('.autoCompleteError').length == 0) $('<span class="autoCompleteError"><p class="alert error">Search autocomplete is currently not responding. Please try again later.</p></span>').insertAfter($("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba")); } } }); }, html: true, delay: 500, select: function (event, ui) { $(this).val(ui.item.value); $(this).next().click(); } }); $searchField.data("ui-autocomplete")._renderItem = function (ul, item) { return $("<li class=\"itemList\"></li>").data("ui-autocomplete-item", item).append("<a>" + item.label + "</a>").appendTo(ul); };}} catch(e) {} //we're going to eat this error. Autocomplete won't work but we dont wan't to break anything else on the page. }); </script>  [![Search](images/ad23c84baf3bd9c160ae4646d88f899251fe74719b13e7287c813e1fabde5475)](https://www.spokanevalleywa.gov/Search/Results) Search <script type="text/javascript"> //Updates search icons href to have the correct queryString function searchBtnApplyQuery() { document.getElementById("btnSearchIcon").href = "/Search?searchPhrase=" + document.getElementById("searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").value; } </script> 

 1.  [Government](https://www.spokanevalleywa.gov/27/Government) 
 1.  [Community](https://www.spokanevalleywa.gov/31/Community) 
 1.  [Business](https://www.spokanevalleywa.gov/101/Business) 
 1.  [Services](https://www.spokanevalleywa.gov/149/Services) 
 1.  [How Do I...](https://www.spokanevalleywa.gov/9/How-Do-I) 
<script type="text/javascript"> document.addEventListener('DOMContentLoaded',function () { var menuID = 'mainNavMenu'; var menuType = MAIN_MENU; //setup menu manager properties for main menu if (!menuManager.mobileMainNav && true) menuManager.adjustMainItemsWidth('#' + menuID); menuManager.isMainMenuEditable = false; menuManager.mainMenuMaxSubMenuLevels = 4; menuManager.setMOMMode(2, menuType); //Init main menu var setupDraggable = menuManager.isMainMenuEditable; var urlToGetHiddenMenus = '/Pages/MenuMain/HiddenMainSubMenus?pageID=1&moduleID=&themeID=1&menuContainerID=mainNav'; menuManager.setupMenu(menuID, 'mainNav', menuType, setupDraggable, urlToGetHiddenMenus); menuManager.mainMenuInit = true; menuManager.mainMenuTextResizer = false; if (1.00 > 0) menuManager.mainMenuTextResizerRatio = 1.00; if (window.isResponsiveEnabled) menuManager.mainMenuReady.resolve(); }); </script>  []()  []()  <script type="text/javascript"> $(window).on("load", function () { $.when(window.Pages.rwdSetupComplete).done(function () { renderExternalBannerSlideshow('banner1', {"BannerOptionID":2,"ThemeID":1,"SlotName":"banner1","Name":"Default","IsDefault":true,"BannerMode":2,"SlideShowSlideTiming":null,"SlideshowTransition":0,"SlideShowTransitionTiming":null,"ImageScale":true,"ImageAlignment":1,"ImageScroll":true,"MuteSound":true,"VideoType":0,"Status":40,"SlideshowControlsPosition":0,"SlideshowControlsAlignment":0,"SlideshowBannerControlsColorScheme":0,"DisplayVideoPauseButton":false,"VideoPauseButtonAlignment":1,"VideoPauseButtonControlsAlignment":0,"VideoPauseButtonStyle":"#FFFFFF","VideoPauseButtonBackgroundStyle":"#000000","VideoPauseButtonAlignmentClass":"alignRight viewport","DisplaySlideshowPauseButton":true,"SlideshowControlsColor":"#FFFFFF","SlideshowControlsBackgroundColor":"#000000","SlideshowPauseButtonClass":"isHidden","BannerImages":[{"BannerImageID":57,"BannerOptionID":2,"FileName":"/ImageRepository/Document?documentID=65","Height":700,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":1,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/","AltText":""},{"BannerImageID":58,"BannerOptionID":2,"FileName":"/ImageRepository/Document?documentID=64","Height":700,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":2,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/","AltText":""},{"BannerImageID":59,"BannerOptionID":2,"FileName":"/ImageRepository/Document?documentID=63","Height":700,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":3,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/","AltText":""}],"BannerVideos":[],"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/"}, '/App_Themes/Interior/Images/', 'Rotating'); }); }); </script> 

 1.  [Home](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities) 
 1.  [Government](https://www.spokanevalleywa.gov/27/Government) 
 1.  [Departments](https://www.spokanevalleywa.gov/186/Departments) 
 1.  [Finance Department](https://www.spokanevalleywa.gov/187/Finance-Department) 
 1. Grant Funding Opportunities

# Grant Funding Opportunities

 1.  [Lodging Tax Grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_0) 
 1.  [Economic Development / Social Service Grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_1) 
 1.  [American Rescue Plan (ARPA) grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_2) 
 1.  [housing & homeless grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_3) 

 1.  [Lodging Tax Grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_0) 

# Lodging Tax Grants

Lodging tax revenues are generated by a tax imposed on overnight stays at hotels and motels within the city. Revenues are dedicated specifically to funding capital projects for tourism-related facilities owned by municipalities and public facilities districts, and tourism-related events and marketing activities. The source of funds is a 2.0 percent tax (RCW 67.28.180) and a 1.3 percent tax (RCW 67.28.181) on all charges for furnishing lodging at hotels, motels, and similar establishments (including bed and breakfasts and RV parks) for a continuous period of less than one month. Funds from the 1.3 percent tax may only be allocated for capital purposes for tourism-related facilities and are only available to municipalities and public facilities districts. 

State law allows the use of lodging tax revenues for the following:

 * Tourism marketing
 * Marketing and operations of special events and festivals
 * Operation and capital expenditures of tourism-related facilities owned or operated by a municipality or public facility district
 * Operation (but not capital expenditures) of tourism-related facilities owned or operated by non-profit organizations

Historically, the City has utilized a percentage of lodging tax proceeds to provide grants to area organizations/agencies tourism related projects. The expected outcome of such activity is to increase economic activity in the City of Spokane Valley through a variety of activities, such as overnight lodging of tourists ("heads in beds"), restaurant sales and retail activity.  

## 2025 Lodging Tax Grants

On Jan. 7, 2025, the City Council unanimously approved the Lodging Tax Advisory Committee (LTAC) recommendations for the 2025 Lodging Tax grant funding. The allocations from the 2% portion of the available funds are:

 * Spokane Valley HUB – Events and Tourism - $147,000
 * 21^(st) USA West Square Dance Convention – Square Dance Convention - $30,000
 * Spokane Regional Sports Commission – Sports Request - $35,000
 * JAKT Foundation – Crave! Event 2025 - $50,000
 * Washington State Quilters – Quilt Show Expansion - $25,000
 * Spokane Valley Summer Theatre – Marketing - $35,000
 * Spokane Valley Heritage Museum - $27,268
 * CNC Productions, LLC – Inland Northwest RV Show & Sale - $11,000
 * Spokane Corvette Club – Glass on Grass - $15,000
 * Cody Productions, Inc – Spokane Motorcycle Show & Sale - $11,000
 * Spokane Co Fair & Expo Center – Interstate Fair Marketing & Safety - $6,732

Additionally, the City of Spokane Valley, in partnership with Spokane Sports, was allocated up to $2.5 million toward the future Spokane Valley Cross Country Course. This funding was awarded from the 1.3% tax portion, which is specifically restricted by the City Council to be used solely for capital expenditures for acquiring, constructing, improving or other related capital expenditures for large sporting venues or tourism-related facilities.

|
|
|

## 2025 Lodging Tax Grant Funding Request for Proposal

 __The application period is now closed.  __ 

The City of Spokane Valley seeks proposals that promote and encourage tourism in Spokane Valley in 2025. The City Council prefers to consider proposals to fund projects in two categories based upon priority rankings. The categories are as follows: 

 1. Capital expenditures (must be a tourism-related facility-owned or operated by a municipality). The available funding for 2025 is anticipated to be up to $2,554,000.
 1. Tourism marketing and operations for special events and festivals and/or the operations and marketing (not capital expenditures) of tourism-related facilities owned and operated by non-profit organizations or municipalities. The available funding for 2025 is anticipated to be up to $339,000.

You may view the 2025 City Council goals and priorities for the Lodging Tax Grant funding [here](https://www.spokanevalleywa.gov/DocumentCenter/View/2893/2025-Council-Goals-Document). 

### GENERAL GUIDELINES 

The 2025 application and instructions are now available. See the table below for important dates.   

###  __Step 1:  __  __View the Request for Proposal (RFP).  __ 

Review the [full RFP](https://www.spokanevalleywa.gov/DocumentCenter/View/2911/2025-RFP---Lodging-Tax-Grant-FINAL-TO-RELEASE) for specific instructions and guidelines regarding the 2025 Lodging Tax Grant application and funding.

###  __Step 2:__  __ Prepare the required documents to be uploaded with your application. __ 

These must be saved in PDF format, and you must complete the entire application once started, as you cannot save the application and return to complete it later.  

REQUIRED: 1) Business Statement, 2) Project Summary, 3) Detailed Project Budget, 4) Scope of Work, 5) Impact on Tourism ( [USE THIS TEMPLATE](https://www.spokanevalleywa.gov/DocumentCenter/View/2892/Impact-on-Tourism---Estimates) ), 6) Goals and Metrics, 7) Project Authorization, 8) Board of Directors/Principal Staff

OPTIONAL SUPPLEMENTAL MATERIALS: 9) Annual Operational Budget, 10) Additional Presentation Materials __ __ 

###  __Step 3:__  __ Plan to attend one of the new virtual Technical Workshop Sessions. __ 

View the previously recorded Technical Workshop:

 *  [Wednesday, Oct. 2, 2024: 1 pm: LTax Grant Application Workshop #2](https://spokanevalley.granicus.com/player/clip/1446?view_id=3&redirect=true) 

###  __Step 4: Complete the application.__ 

Be sure to upload all required PDF documentation and complete the application in one session. IT CAN NOT BE SAVED TO RETURN TO AT A LATER TIME.   

###  __APPLICATION TIMELINE: __ 

Applications are due by 4 p.m. on Monday, Oct. 14, 2024

|Lodging Tax Grant funding release|Sept. 16, 2024|
|---|---|
|Application/Proposal submission deadline|4 pm on Oct. 14, 2024|
|Proposal Packets finalized for Lodging Tax Advisory Committee (LTAC)|Oct. 25, 2024|
|Lodging Tax Advisory Committee (LTAC) meets, hears presentations, and makes award recommendations that will be forwarded to the City Council|Nov. 4, 2024|
|Administrative Report to City Council regarding LTAC recommendation|Nov. 19, 2024|
|City Council Motion Consideration for 2025 awards|Jan. 7, 2025|
|Contracts completed|Feb. 2025|
|Date by which projects must be completed|Dec. 31, 2025|
|Post-event/Project reporting due (must accompany final reimbursement request)|Dates vary – no later than Jan. 31, 2026|

## 

## Lodging Tax Advisory Committee

The recipients of these grants are determined by City Council, after receiving a list of recommended allocations for funding from the Lodging Tax Advisory Committee (LTAC). The LTAC is comprised of five members who are appointed by City Council, and by state law the committee membership must include:

 * At least two representatives of businesses that are required to collect the tax
 * At least two people who are involved in activities that are authorized to be funded by the tax, and 
 * One elected city official who serves as chairperson of LTAC

Annually, the City Council discusses and adopts goals and priorities that it encourages the Lodging Tax Advisory Committee (LTAC) to consider when making award recommendations. [Here are the Council goals for the 2025 award year](https://www.spokanevalleywa.gov/DocumentCenter/View/2893/2025-Council-Goals-Document). Applicants are encouraged to create proposals that are aligned with the Council’s goals and priorities. 

The LTAC develops recommendations after reviewing a combination of submitted application materials and hearing a brief presentation made by each applicant. Grants are awarded annually. Applicants may view a sample grant agreement contract [here](https://www.spokanevalleywa.gov/DocumentCenter/View/2919/Lodging-Tax-Grant-Agreement-2025-FINAL-Template-SAMPLE-FOR-WEBPAGE).

## Past Awards - 2024 Grant Recipients

On December 12, 2023, the City Council reached a consensus to make a final determination of awards for the 2024 Lodging Tax Grant funding. The allocations from the 2% portion of the available funds are as follows:

 * Cody Productions – up to $8,250
 * CNC Productions– up to $7,000
 * Family Guide – up to $12,000
 * JAKT - Crave! – up to $48,750
 * JAKT - Farmer's Market – up to $12,250
 * Northwest Winterfest – up to $36,250
 * Spokane Conservation District – up to $20,750
 * Spokane Co Fair and Expo Center– up to $55,250
 * Spokane Valley Heritage Museum – up to $26,125
 * Spokane Valley HUB Sports Center – up to $147,000
 * Spokane Valley Summer Theatre - up to $25,000
 * Victory Media – up to $38,750
 * Washington State Quilters Spokane Chapter– up to $17,500
 * WinterGlow Spectacular – up to $3,750

Additionally, the City of Spokane Valley, in partnership with Spokane Sports, was allocated up to $4.4 million for the design, construction, and other associated costs of the City of Spokane Valley and Spokane Sports Cross Country Course Project.  This funding was awarded from the 1.3% tax portion, which is specifically restricted by the City Council to be used solely for capital expenditures for acquiring, constructing, making improvements to or other related capital expenditures for large sporting venues or tourism-related facilities.

|
|
|

 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + 'd67a4898-5561-45b8-9f66-a3eb723f4aee')); });</script> 

 1.  [Economic Development / Social Service Grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_1) 

# Economic Development/Social Service Grants

The Spokane Valley City Council has historically included funds in the annual budget to contract with organizations to support economic development activities and social service efforts that directly benefit the citizens of Spokane Valley. 

##  __2025 Grant Program Update __  __as of January 2025__ 

Due to city revenues not keeping pace with expenditures, the Economic Development and Social Services Grant Program was not funded in the 2025 budget. The program will be reevaluated during 2026 budget preparations and an update will be posted here. 

## 2024 Program

The City Council allocated a total of $200,000 with $100,000 available in each category for separate consideration. Recipients are non-profit organizations that have received 501(c)(3) or (6) federal tax-exempt status from the U.S. Internal Revenue Service (IRS) and are registered as a non-profit corporation in the State of Washington.

### 2024 Grant Recipients

On Oct 24, 2023, the City Council reached a consensus to make a final determination of awards for the 2024 Economic Development and Social Services Grants funding. The allocations are as follows:

###  __Outside Agency Grant: Economic Development__ 

 * Idaho Central Spokane Valley Performing Arts Center - up to $8,886
 * JAKT Foundation - CRAVE - up to $7,857
 * JAKT Foundation - Farmers Market - up to $13,600
 * SNAP Financial Access - up to $19,171
 * Spokane Valley Arts Council - up to $11,000
 * Spokane Valley Heritage Museum - up to $18,457
 * Spokane Valley Summer Theatre - up to $13,886
 * Spokane Workforce Council - up to $7,143

###  __Outside Agency Grant: Social Services__ 

 * Christ Kitchen - up to $5,571
 * Elevations Childrens Therapy - up to $15,238
 * Inland Chess Academy - up to $1,857
 * Joya Child and Family Development - up to $5,757
 * NAOMI - up to $9,810
 * Spokane Valley Partners - up to $30,982
 * Teen and Kid Closet - up to $12,000
 * Widows Might - up to $15,714
 * YMCA of the Inland Northwest - up to $3,071
 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + '64290194-8faf-4d63-95e1-7e704fbe43ba')); });</script> 

 1.  [American Rescue Plan (ARPA) grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_2) 

# American Rescue Plan Act funding

The city has received approximately $16 million of American Rescue Plan Act funding to address impacts from the COVID-19 Pandemic. On May 31, 2022, City Council allocated the funding to a variety of uses to help address impacts in Spokane Valley.  Approved uses include: 

City Council is continuing to work towards distributing remaining funds. Please continue to check back for potential ARPA grant funding opportunities.

### $630,000 for the Buckeye Avenue Sewer Extension Project

Completed in 2022.  

### $1 million grant to Innovia LaunchNW Foundation

An initiative to aid youth at various levels to increase the number of youth attending post-secondary education, vocational/trade education, or training.

 January 28, 2025 Update: Ben Small, Executive Director of LaunchNW spoke about the MPower mentoring program, including wraparound services and supports enhancement within the current system of providers for students and families in participating districts which currently include East Valley and University High School.  He also reported successful development of a financial model for a tuition only scholarship program, a public facing data dashboard which features key educational indicators for students in Spokane County, and in-school case managers provided by a partner organization, Family Promise.  Mr. Small also mentioned plans for the organization to increase student participation by adding two more Spokane Valley Schools to the LaunchNW mentoring program. 

### Approximately $960,000 for law enforcement assistance

Specific uses included purchase of two camera trailers, additional overtime emphasis patrols as part of the Regional Safe Streets Task Force, and acquisition of cameras to improve park security. 

### $4 million grant to Spokane Valley Partners for acquisition of a new facility.

July 30, 2024 Update: Dr. Cal Coblentz, Chief Executive Officer of Partners Inland NW spoke about the substantial increases in the food bank, clothing bank, and related services in the community.  He noted a 91% growth in the number of people fed since 2019. Dr. Coblentz then updated the Council on the progress of the new facility and how city funds have been utilized thus far. Partners finalized the purchase of a building on E. Sprague Avenue in February of 2023, and have been using a portion of the building to store some inventory for their food and diaper programs. The organization is in the process of securing additional funding to finish renovating the space and anticipates occupancy sometime during 2026.  

### Approximately $780,000 grant to the Idaho Central Spokane Valley Performing Arts Center construction project

July 30, 2024 Update: Dr. Marie Rorholm, ICSVPAC Managing Director, reported that city funding was spent on the building foundation and infrastructure (sewer, water, electrical, etc.). She provided an overview of the programs provided by the organization to the community, statistics on patron and student attendance, and the amount of funding raised/spent toward the Performing Arts Center project. Dr. Rorholm addressed the delays to the project, explained a new phased building plan, and noted that ICSVPAC has now contracted with Walker Construction and expects to resume work on the site in early fall 2024. She noted that the facility is scheduled to open in fall 2025.

 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + '9bf0b541-3959-4dbf-9d38-18e501075063')); });</script> 

 1.  [housing & homeless grants](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities#tabbb008891-9865-4804-bd5c-d448050564da_3) 

#  __Housing and Homeless Grants__ 

The Spokane Valley City Council allocated approximately $4 million in grants from the general fund for affordable housing and homeless-related projects. Grant recipients include:

### $1 million to Family Promise for its F.L.A.S.H. fast leasing and sustainable housing program

July 30, 2024 Update: Mr. Joe Ader from Family Promise shared updates regarding the progress of this pilot program and their projects and shared statistics about how many people have been served by their organization, the cost difference in FLASH vs. traditional shelter-based services and the next steps. Mr. Ader highlighted the school-based case managers and the successes of the in-school prevention program in the Valley schools. He reported that the initial projections were to serve 25 families with the city’s funding, and with six months remaining the organization has already served 52 families. Additionally, the average days of homelessness in the FLASH program is only six compared to an average of 75 days in the emergency shelter. Mr. Ader attributes the success of the FLASH program to the flexibility of the funding, rapid intervention, and that the funding is attached to the family, not the program. He is excited to share that Family Promise hopes to secure further funding from additional sources to continue the FLASH program and research the outcomes in greater detail.

### $1.4 million to Reclaim Project Recovery for its home base facility, operations and a transitional housing facility in Spokane Valley

July 30, 2024 Update:  Update: Mr. Kenny Carlson from Reclaim Project Recovery spoke about how they have utilized the funding to lease a new home base location in the Spokane Valley, where the organization has opened a thrift store to create job training opportunities and partner with other service providers in providing community needs.   He also spoke of the various activities available in the programs provided, including recreation and support to the clients. Mr. Carlson also reported that with the coordination of the city’s funding and a grant from Spokane County, Reclaim recently closed on the purchase of property for transitional housing. The anticipated occupancy date is early 2025, and any remaining funding from the city’s grant in this budget item may be used for an additional site for transitional housing in Spokane Valley.

### $500,000 to Volunteers of America for its Crosswalk 2.0; a youth transitional housing project

 January 28, 2025 Update: Fawn Schott, President/CEO of Volunteers of America of Eastern WA Northern ID spoke about the construction of the Crosswalk 2.0 Teen Shelter.  Crosswalk is an expanded service model that includes an emergency shelter for youth aged 16-20.  With the facility’s proximity to Spokane Community College, Crosswalk 2.0 will also include college dorms for the youth who are engaged in Spokane Community College’s career readiness degree and running start programs.  On-site programming will be offered including services from case managers, teachers, health care workers, and counselors.  Ms. Schott also spoke about the anticipated completion and occupancy in Fall of 2025. 

### $470,000 to Habitat for Humanity for acquisition of property to provide affordable housing in Spokane Valley

January 28, 2025 Update: Eric Lyons, Chief Operating Officer, and Colleen Weedman, Chief Program Director for Habitat Spokane, spoke about the progress of the project funded by the City’s award.  Habitat was able to acquire four (4) lots within the City of Spokane Valley which are being used to develop seven (7) units of housing that are affordable to households with incomes at or below 80% area median income (AMI).  Homebuyers must complete the homeownership program, including pre-purchase education, credit & budget management and closing procedures to qualify for Habitat’s program and purchase a home. Mr. Lyons and Ms. Weedman also spoke the program’s long-term benefits utilizing a 99-year land trust to ensure affordability limits remain with the housing.

### $470,000 to SNAP for its Broadway Senior Affordable Housing Project

 January 28, 2025 Update Amber Johson, Chief Operating Officer for SNAP, spoke about the Broadway Senior Housing project funded in part by the City’s allocation from the Affordable Housing and Homeless Grants. This facility, anticipated for completion in 2027, will consist of a four-story, corridor loaded building with two elevators, providing 57 one-bedroom units and three two-bedroom units.  The project will provide permanent rental housing and supportive services to seniors with incomes at or below 60% of the area median household income.  Additionally, in several of the units, seniors will be provided with rent subsidy and only pay 30% of their adjusted gross income in rent.  Ms. Johnson explained some of the project’s delays related to other sources of funding and SNAP’s potential plans for alternate options as necessary to continue with the current schedule.  The organization plans to break ground on the project in December 2025.    

 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + 'bf5a8a40-939e-412a-9d9c-1f38e946100f')); });</script> <script type="text/javascript">  $.when(window.Pages.rwdReady).done(function () { var tabbedWidgetID = 'divTabbedbb008891-9865-4804-bd5c-d448050564da'; var mediaQuerySize = 25; if (mediaQuerySize > 0) { var mediaElementQuery = '#' + tabbedWidgetID + ':media(this-min-width:' + mediaQuerySize + 'em)'; var $tabbedWidget = $('#' + tabbedWidgetID); window.cpMedia.unregister(mediaElementQuery).register(mediaElementQuery, { deferSetup: false, setup: function () { var liveEditEnabled = $.cookie("enableLiveEdit") === "true"; if (!liveEditEnabled) { $tabbedWidget.addClass('narrow').removeClass('wide'); cpMedia.diag('$(element).addClass("narrow"), mediaQuery: ' + mediaElementQuery); $tabbedWidget.find('.tabbedWidget.cpTabs').hide(); $tabbedWidget.find('.tabbedWidgetNarrow.cpTabs').show(); $tabbedWidget.data("tabHeightSet", false); } }, match: function () { $tabbedWidget.addClass('wide').removeClass('narrow'); cpMedia.diag('$(element).removeClass("narrow"), mediaQuery: ' + mediaElementQuery); $tabbedWidget.find('.tabbedWidget.cpTabs').show(); $tabbedWidget.find('.tabbedWidgetNarrow.cpTabs').hide(); if($tabbedWidget.data("tabHeightSet") == false) { $tabbedWidget.data("tabHeightSet", true); var tabbedWidgetID = 'divTabbedbb008891-9865-4804-bd5c-d448050564da'; setTabbedWidgetsTabHeight(tabbedWidgetID); } $('.cpTabPanels').unbind('click'); }, unmatch: function () { var liveEditEnabled = $.cookie("enableLiveEdit") === "true"; if (!liveEditEnabled) { $tabbedWidget.addClass('narrow').removeClass('wide'); cpMedia.diag('$(element).addClass("narrow"), mediaQuery: ' + mediaElementQuery); $tabbedWidget.find('.tabbedWidget.cpTabs').hide(); $tabbedWidget.find('.tabbedWidgetNarrow.cpTabs').show(); } $('.cpTabPanels').click(function() { this.scrollIntoView(); }); } }); } });   //Used for when page is initially loaded if($('#divTabbedbb008891-9865-4804-bd5c-d448050564da').hasClass('narrow')) { $('.cpTabPanels').click(function() { this.scrollIntoView(); }); }  //If responsive not enabled, execute this after a timeout if(!isResponsiveEnabled) { window.setTimeout(function(){ var tabbedWidgetID = 'divTabbedbb008891-9865-4804-bd5c-d448050564da'; typeof setTabbedWidgetsTabHeight === "function" && setTabbedWidgetsTabHeight(tabbedWidgetID); }, 1500); } function reinitCarousels() { if (window.carouselsToInit) { for (var i = 0; i < window.carouselsToInit.length; i++) { carouselsToInit[i](); } } } function sizeTabbedContent(element){ if(window.Pages){ if(window.Pages.onResizeHandlers){ var setTabbedInterval = setInterval(function () { window.Pages.onResizeHandlers.forEach(function(car){car();}); }, 25) setTimeout(function () { clearInterval(setTabbedInterval); if ($.cookie("enableLiveEdit") === "true") { setInterval(function () { window.Pages.onResizeHandlers.forEach(function(car){car();}); }, 2000); } }, 2500); element.onclick="window.setTimeout(function(){reinitCarousels();},2);" } } } function adjustTab(e) { e.preventDefault(); window.setTimeout(function(){ reinitCarousels(); }, 2); sizeTabbedContent(this); } var tabButtons = document.querySelectorAll("#divTabbedbb008891-9865-4804-bd5c-d448050564da.tabButton"); tabButtons.forEach(function (tabButton) { tabButton.addEventListener("click", adjustTab); }); </script> 

## Resource Directory

 *  [Request for Proposals (RFP)](https://www.spokanevalleywa.gov/DocumentCenter/View/2911/2025-RFP---Lodging-Tax-Grant-FINAL-TO-RELEASE) 
 *  [Impact on Tourism Template](https://www.spokanevalleywa.gov/DocumentCenter/View/2892/Impact-on-Tourism---Estimates) 
 *  [Council Goals and Priorities](https://www.spokanevalleywa.gov/DocumentCenter/View/2893/2025-Council-Goals-Document) 
 *  [Sample Agreement](https://www.spokanevalleywa.gov/DocumentCenter/View/2919/Lodging-Tax-Grant-Agreement-2025-FINAL-Template-SAMPLE-FOR-WEBPAGE) 
 *  [Lodging Tax Workshop](https://spokanevalley.granicus.com/player/clip/1446?view_id=3&redirect=true) 

 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + 'e245fb91-9a32-4314-a0d5-1022a777ac12')); });</script> 

###  [Contact Us](https://www.spokanevalleywa.gov/Directory.aspx) 

 1.    

#### Sarah Farr   

 Accounting & Finance Program Manager  [Email Sarah Farr](mailto:sfarr@SpokaneValleyWA.gov)  Phone: [509-720-5041](tel:5097205041)     

 1.   [Budget & Financial Reports](https://www.spokanevalleywa.gov/188/Budget-Financial-Reports)  
 1.   [Grant Funding Opportunities](https://www.spokanevalleywa.gov/190/Grant-Funding-Opportunities)  
 1.   [Spokane Valley Tax Rates](https://www.spokanevalleywa.gov/191/Spokane-Valley-Tax-Rates)  
<script type="text/javascript"> window.addEventListener('load', function () { //setup menu manager properties for secondary menu menuManager.isSideMenuEditable = false; menuManager.sideMenuMaxSubMenuLevels = 4; menuManager.sideMenuHasCustomLinks = false; }); </script><script type="text/javascript"> window.addEventListener('load', function () { $('*[id^="SideItem"]').each(function () { var ids = $('[id="' + this.id + '"]'); if (ids.length > 1) $.each(ids, function (index, value) { value.id = value.id + '_' + index; }); }); $('.hasAccordionChildren.openAccordionNav').click(function (e) { e.preventDefault(); showHideAccordionMenuForSecondaryNav($(this)); }); $("#secondaryNav.grippy").each(function () { menuManager.setupDraggableElement($(this), SIDE_MENU, '#secondaryNav'); }); $("#secondaryNav li").each(function () { menuManager.setupDroppableAccordionElement($(this), SIDE_MENU); }); }); </script>  [Permit Center](https://www.spokanevalleywa.gov/180/Permit-Center)   [Police Department](https://www.spokanevalleywa.gov/169/Police)   [Parks & Recreation](https://www.spokanevalleywa.gov/163/Parks-Recreation)   [Employment](https://www.spokanevalleywa.gov/411)   [Agendas & Minutes](https://www.spokanevalleywa.gov/129/Agendas-Minutes)   [Report a Concern](https://www.spokanevalleywa.gov/443/SVexpress---Report-a-Concern)  

 1.    

 ![Home Page](images/026af6a61a5ac689510b60b6fc66b0f3f9732d306d5983a5da3be8cb6c1d79a0)    

 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdv4cd3f3bf-9fee-4aaa-aa8b-3d56fdc3415a.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

### Contact Us

 1.    

 __Spokane Valley City Hall__    

10210 East Sprague Avenue   

Spokane Valley, WA 99206   

 __Phone__ : [509-720-5000](tel: 509-720-5000)    

 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdvbcf5407d-f091-4078-83b2-29c769f2420b.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

###  [Quick Links](https://www.spokanevalleywa.gov/QuickLinks.aspx?CID=15) 

 1.  [News & Alerts - Subscribe](https://public.govdelivery.com/accounts/WASPOKANEVALLEY/subscriber/new?qsp=CODE_RED)  
 1.  [Public Notices](https://www.spokanevalleywa.gov/359/2154/Public-Notices)  
 1.  [Public Records Request](https://spokanevalleywa.gov/691/Public-Records)  
 1.  [Documents Archive (Laserfiche)](https://laserfiche.spokanevalley.org/WebLink/Browse.aspx?dbid=0&repo=SpokaneValley)  
 1.  [Municipal Code](https://www.codepublishing.com/WA/SpokaneValley)  
 1.  [City News](https://www.spokanevalleywa.gov/CivicAlerts.aspx?CID=1)  
 /QuickLinks.aspx 

###  [Site Links](https://www.spokanevalleywa.gov/QuickLinks.aspx?CID=16) 

 1.  [City Home](https://www.spokanevalleywa.gov)  
 1.  [Contact Us](https://www.spokanevalleywa.gov/directory.aspx)  
 1.  [Site Map](https://www.spokanevalleywa.gov/sitemap)  
 1.  [ADA Notification](https://www.spokanevalleywa.gov/207/Americans-with-Disabilities-Act-Notice)  
 1.  [Website Accessibility](https://www.spokanevalleywa.gov/accessibility)  
 1.  [Copyright Notices](https://www.spokanevalleywa.gov/copyright)  
 1.  [Privacy Policy & Data Collection](https://www.spokanevalleywa.gov/privacy)  
 /QuickLinks.aspx Loading Loading Do Not Show AgainClose <script src="/Assets/Scripts/APIClient.js"></script><script src="/Assets/Mystique/Shared/Scripts/Moment/Moment.min.js"></script><script src="/Assets/Scripts/SplashModal/SplashModalRender.js"></script><script> $(document).ready(function () { var filter = { targetId: '190', targetType: 1 } new SplashModalRender().triggerRender(filter); });</script><script src="/-1931737305.js" type="text/javascript"></script><script> function getValueTS(elem, attr) { var val = elem.css(attr); if (val === undefined) return undefined; var num = parseInt(val, 10); if (num === NaN) return undefined; return num; } function clampTS(number, min, max) { return Math.min(Math.max(number, min), max); } function isPageEditingTS() { return ( $("#doneEditing").length > 0 || // In live edit typeof DesignCenter !== "undefined" // In theme manager ); } var bgColorRegexTS = new RegExp("rgba\((\d+), (\d+), (\d+), (\d*\.?\d*)\)"); function isTransparentTS(elem) { var bg = elem.css('background-color'); if (typeof bg !== "string") return false; if (bg === "transparent") return true; if (!bg.startsWith('rgba(')) return false; var matchState = bg.match(bgColorRegexTS); if (!matchState || matchState.length !== 5) return false; var alpha = parseFloat(matchState[4], 10); if (!(alpha >= 0 && alpha < 1)) return false; return true; } function iterateLeftpads(cb) { var containersTS = $("[class^='siteWrap'],[class*=' siteWrap']"); for (var i = 0; i < containersTS.length; i++) { var containerTS = containersTS[i]; // Skip the body container and anything with data-skip-leftpad if ( containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-leftpad') === null ) { cb(containerTS); } } } function iterateRightpads(cb) { var containersTS = $("[class^='siteWrap'],[class*=' siteWrap']"); for (var i = 0; i < containersTS.length; i++) { var containerTS = containersTS[i]; // Skip the body container and anything with data-skip-rightpad if ( containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-rightpad') === null ) { cb(containerTS); } } } var anchor = $("#divToolbars"); var bodyContainerTS = $("#bodyContainerTS"); // Outer banner padding (push banner down) var outerSizingTS = $("#bannerContainerTS"); // Inner banner padding (push banner content down) - Transparent header OR on attaching headers var innerSizingTS = $("#bannerSizingTS"); var forceUnfixClassTS = "forceUnfixTS"; var fixedTopTS = $(".fixedTopTS"); var fixedBottomTS = $(".fixedBottomTS"); var fixedLeftTS = $(".fixedLeftTS"); var fixedRightTS = $(".fixedRightTS"); var initialTopTS; var topAttachTS; if (fixedTopTS && fixedTopTS.length === 1) { initialTopTS = getValueTS(fixedTopTS, 'top'); var attachment = fixedTopTS.attr('data-attach'); if (attachment) topAttachTS = $("#" + attachment); if (!topAttachTS || topAttachTS.length !== 1) topAttachTS = undefined; } function resizeAdjustmentTS() { var editing = isPageEditingTS(); // Fixed top script (function () { if (!fixedTopTS || fixedTopTS.length !== 1 || initialTopTS === undefined) return; if (editing) { fixedTopTS[0].classList.add(forceUnfixClassTS); } else { fixedTopTS[0].classList.remove(forceUnfixClassTS); } var topPosition = fixedTopTS.css('position'); if (topPosition === 'fixed') { if (topAttachTS) { scrollAdjustmentTS(); } else { var anchorHeight = anchor.outerHeight() - 1; fixedTopTS.css('top', anchorHeight + initialTopTS); } } else { fixedTopTS.css('top', initialTopTS); } if (topPosition === 'fixed' || topPosition === 'absolute') { // Bump the banner content down if (isTransparentTS(fixedTopTS)) { innerSizingTS.css('padding-top', initialTopTS + fixedTopTS.outerHeight()); outerSizingTS.css('padding-top', ''); try { window.Pages.onResizeHandlersExecute(); } catch (e) { } } else { outerSizingTS.css('padding-top', fixedTopTS.outerHeight() - 1); innerSizingTS.css('padding-top', ''); } } else { innerSizingTS.css('padding-top', ''); outerSizingTS.css('padding-top', ''); } })(); // Fixed bottom script (function () { if (!fixedBottomTS || fixedBottomTS.length === 0) return; // If the widget has gone narrow, force unfix if (editing || fixedBottomTS.outerHeight() > 200) { fixedBottomTS[0].classList.add(forceUnfixClassTS); } else { fixedBottomTS[0].classList.remove(forceUnfixClassTS); } if (fixedBottomTS.css('position') === 'fixed') { bodyContainerTS.css('padding-bottom', fixedBottomTS.outerHeight()); } else { bodyContainerTS.css('padding-bottom', ''); } })(); // Fixed left script (function () { if (!fixedLeftTS || fixedLeftTS.length === 0) return; if (editing) { fixedLeftTS[0].classList.add(forceUnfixClassTS); } else { fixedLeftTS[0].classList.remove(forceUnfixClassTS); } if (fixedLeftTS.css('position') === 'fixed') { var anchorHeight = anchor.outerHeight() - 1; fixedLeftTS.css('top', anchorHeight); var leftBoundingTS = fixedLeftTS[0].getBoundingClientRect(); iterateLeftpads(function (containerTS) { var containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.left <= leftBoundingTS.right) { $(containerTS).css('padding-left', leftBoundingTS.width + 16); } else { $(containerTS).css('padding-left', ''); } }); } else { fixedLeftTS.css('top', ''); iterateLeftpads(function (containerTS) { $(containerTS).css('padding-left', ''); }); } })(); // Fixed right script (function () { if (!fixedRightTS || fixedRightTS.length === 0) return; if (editing) { fixedRightTS[0].classList.add(forceUnfixClassTS); } else { fixedRightTS[0].classList.remove(forceUnfixClassTS); } if (fixedRightTS.css('position') === 'fixed') { var anchorHeight = anchor.outerHeight() - 1; fixedRightTS.css('top', anchorHeight); var rightBoundingTS = fixedRightTS[0].getBoundingClientRect(); iterateRightpads(function (containerTS) { var containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.right >= rightBoundingTS.left) { $(containerTS).css('padding-right', rightBoundingTS.width + 16); } }); } else { fixedRightTS.css('top', ''); iterateRightpads(function (containerTS) { $(containerTS).css('padding-right', ''); }); } })(); } function scrollAdjustmentTS() { if (!fixedTopTS || fixedTopTS.length !== 1 || !topAttachTS || topAttachTS.length !== 1) return; var topPosition = fixedTopTS.css('position'); if (topPosition === 'fixed' || topPosition === 'absolute') { var anchorBounding = anchor[0].getBoundingClientRect(); var attachBounding = topAttachTS[0].getBoundingClientRect(); var scrollTop = $(window).scrollTop(); fixedTopTS.css('top', Math.max(anchorBounding.bottom - 1, attachBounding.bottom)); } else { fixedTopTS.css('top', initialTopTS); } } $(window).load(function () { setTimeout(function () { try { resizeAdjustmentTS(); } catch (e) { console.error(e); } }, 350); $(window).scroll(function () { try { scrollAdjustmentTS(); } catch (e) { console.error(e); } }); var adjustTimeoutTS; $(window).resize(function () { clearTimeout(adjustTimeoutTS); adjustTimeoutTS = setTimeout(function () { try { resizeAdjustmentTS(); } catch (e) { console.error(e); } }, 350); }); $.when(window.Pages.angularToolbarComplete).done(function () { try { resizeAdjustmentTS(); } catch (e) { console.error(e); } }); });</script><script type="text/javascript"> $(function () { document.cookie = "responsiveGhost=0; path=/"; }); $(window).on("load", function () { $('body').addClass('doneLoading').removeClass('hideContent'); if ($('#404Content').length > 0) $('div#bodyWrapper').css('padding', '0px'); }); </script> <script type="text/javascript">loadCSS('//fonts.googleapis.com/css?family=DM+Serif+Display:italic,regular|Open+Sans:300,300italic,500,500italic,600,600italic,700,700italic,800,800italic,italic,regular|');</script> [] 